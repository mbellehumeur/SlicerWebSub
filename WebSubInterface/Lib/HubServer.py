"""Slicer WebSub — Hub subsection (embedded Slicer hub server UI)."""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import tempfile
import zipfile
from typing import Optional
from urllib.parse import quote
from urllib.request import urlretrieve

import qt

from slicer.i18n import tr as _
import slicer

DEFAULT_HUB_PORT = 2018

_STATUS_TEXT_STYLE_IDLE = "color: palette(text);"
_STATUS_TEXT_STYLE_RUNNING = "color: palette(link);"
_STATUS_TEXT_STYLE_ERROR = "color: palette(negative);"

from .python_deps import DepsDeclinedError as HubDepsDeclinedError
from .python_deps import ensure_module_python_deps
from .repo_paths import ensure_monorepo_import_paths, hub_dir, hub_script

SPA_CLIENTS_RELEASE_URL = (
    "https://github.com/mbellehumeur/SlicerWebSub/releases/tag/spa-clients"
)
SPA_CLIENTS_ZIP_URL = (
    "https://github.com/mbellehumeur/SlicerWebSub/releases/download/"
    "spa-clients/spa-clients.zip"
)


def _ensure_hub_deps() -> None:
    """Install hub/client deps into Slicer Python (action-time confirm)."""
    ensure_module_python_deps(requester="WebSubInterface Hub")


def _is_windows() -> bool:
    return sys.platform == "win32"


def _hub_port_from_spin(spin: Optional[qt.QSpinBox]) -> int:
    if not spin:
        return DEFAULT_HUB_PORT
    return int(spin.value)


def _port_is_listening(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def _win_kill_process_tree(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        result = subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _force_stop_qprocess(proc: qt.QProcess) -> None:
    """Stop hub child process; on Windows use taskkill on the process tree."""
    pid = int(proc.processId()) if proc else 0
    if proc.state() == qt.QProcess.NotRunning:
        if _is_windows() and pid > 0:
            _win_kill_process_tree(pid)
        return
    if _is_windows():
        if pid > 0:
            _win_kill_process_tree(pid)
        proc.kill()
        proc.waitForFinished(5000)
        return
    proc.terminate()
    if not proc.waitForFinished(5000):
        proc.kill()
        proc.waitForFinished(3000)


class HubServerWidget:
    """Hub section UI: start/stop local hub subprocess."""

    def __init__(self) -> None:
        self._section: Optional[qt.QWidget] = None
        self._setup_complete = False
        self._hub_process: Optional[qt.QProcess] = None
        self._hub_pid: int = 0
        self._hub_port: int = DEFAULT_HUB_PORT
        self._stopping: bool = False
        self._hub_admin_token: str = ""
        self._hub_jwt_secret: str = ""

        self.portSpinBox: Optional[qt.QSpinBox] = None
        self.startButton: Optional[qt.QPushButton] = None
        self.stopButton: Optional[qt.QPushButton] = None
        self.openAdminButton: Optional[qt.QPushButton] = None
        self.spaHelpButton: Optional[qt.QPushButton] = None
        self.statusLabel: Optional[qt.QLabel] = None

    def setup(self, section: qt.QWidget) -> None:
        if self._setup_complete:
            return
        self._setup_complete = True
        self._section = section
        layout = qt.QFormLayout(section)
        layout.setLabelAlignment(qt.Qt.AlignLeft)

        self.portSpinBox = qt.QSpinBox()
        self.portSpinBox.setRange(1024, 65535)
        self.portSpinBox.setValue(DEFAULT_HUB_PORT)
        self.portSpinBox.setToolTip(_("TCP port for the local Slicer hub server"))

        self.startButton = qt.QPushButton(_("Start"))
        self.stopButton = qt.QPushButton(_("Stop"))
        self.stopButton.enabled = False
        self.openAdminButton = qt.QPushButton(_("Open Hub Portal"))
        self.openAdminButton.enabled = False
        self.openAdminButton.setToolTip(
            _("Open the hub portal in your default browser")
        )

        port_row = qt.QWidget()
        port_row_layout = qt.QHBoxLayout(port_row)
        port_row_layout.setContentsMargins(0, 0, 0, 0)
        port_row_layout.addWidget(self.portSpinBox)
        port_row_layout.addWidget(self.startButton)
        port_row_layout.addWidget(self.stopButton)
        port_row_layout.addWidget(self.openAdminButton)
        port_row_layout.addStretch(1)
        layout.addRow(_("Port:"), port_row)

        self.statusLabel = qt.QLabel(_("Hub stopped"))
        self.statusLabel.setStyleSheet(_STATUS_TEXT_STYLE_IDLE)
        layout.addRow(_("Status:"), self.statusLabel)

        self.spaHelpButton = qt.QPushButton(_("Download SPA clients…"))
        self.spaHelpButton.setToolTip(
            _(
                "Download browser clients from the GitHub spa-clients release "
                "and extract them into the local hub folder"
            )
        )
        layout.addRow(_("Example applications (SPAs):"), self.spaHelpButton)

        self.startButton.connect("clicked()", self._on_start)
        self.stopButton.connect("clicked()", self._on_stop)
        self.openAdminButton.connect("clicked()", self._on_open_admin)
        self.spaHelpButton.connect("clicked()", self._on_download_spas)

    def _set_status(self, text: str, style: str = _STATUS_TEXT_STYLE_IDLE) -> None:
        if self.statusLabel:
            self.statusLabel.setText(text)
            self.statusLabel.setStyleSheet(style)

    def _open_spa_release_page(self) -> None:
        qt.QDesktopServices.openUrl(qt.QUrl(SPA_CLIENTS_RELEASE_URL))

    def _on_download_spas(self) -> None:
        hub_path = hub_dir()
        hub_path_str = str(hub_path)
        confirmed = slicer.util.confirmOkCancelDisplay(
            _(
                "Download spa-clients.zip (~40 MB) from GitHub and extract into:\n"
                "{hub}\n\n"
                "Existing SPA folders there may be overwritten."
            ).format(hub=hub_path_str),
            windowTitle=_("Download SPA clients"),
        )
        if not confirmed:
            return

        progress = qt.QProgressDialog(
            _("Downloading spa-clients.zip…"),
            _("Cancel"),
            0,
            0,
            self._section,
        )
        progress.setWindowTitle(_("Download SPA clients"))
        progress.setWindowModality(qt.Qt.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()
        qt.QApplication.processEvents()

        cancelled = {"value": False}

        def _on_canceled() -> None:
            cancelled["value"] = True

        progress.canceled.connect(_on_canceled)

        tmp_path = ""
        try:
            fd, tmp_path = tempfile.mkstemp(suffix="-spa-clients.zip")
            os.close(fd)

            def _reporthook(
                block_num: int, block_size: int, total_size: int
            ) -> None:
                if cancelled["value"]:
                    raise InterruptedError("download cancelled")
                if total_size > 0:
                    if progress.maximum() != total_size:
                        progress.setMaximum(total_size)
                    done = min(total_size, block_num * block_size)
                    progress.setValue(done)
                else:
                    progress.setMaximum(0)
                qt.QApplication.processEvents()

            urlretrieve(SPA_CLIENTS_ZIP_URL, tmp_path, reporthook=_reporthook)
            if cancelled["value"]:
                raise InterruptedError("download cancelled")

            progress.setLabelText(_("Extracting into hub folder…"))
            progress.setMaximum(0)
            qt.QApplication.processEvents()
            ensure_monorepo_import_paths()
            from safe_zip import safe_extract_zip

            with zipfile.ZipFile(tmp_path, "r") as zf:
                safe_extract_zip(zf, hub_path_str)
        except InterruptedError:
            progress.close()
            self._set_status(
                _("SPA download cancelled"),
                _STATUS_TEXT_STYLE_IDLE,
            )
            return
        except Exception as exc:
            progress.close()
            self._set_status(
                _("SPA download failed: {0}").format(exc),
                _STATUS_TEXT_STYLE_ERROR,
            )
            open_page = slicer.util.confirmOkCancelDisplay(
                _(
                    "Download or extract failed:\n{err}\n\n"
                    "Open the GitHub release page in your browser?"
                ).format(err=exc),
                windowTitle=_("Download SPA clients"),
            )
            if open_page:
                self._open_spa_release_page()
            return
        finally:
            progress.close()
            if tmp_path and os.path.isfile(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        if self._is_running():
            slicer.util.infoDisplay(
                _(
                    "SPA clients installed into:\n{hub}\n\n"
                    "Stop then Start the hub so mounts reload."
                ).format(hub=hub_path_str),
                windowTitle=_("Download SPA clients"),
            )
            self._set_status(
                _("SPA clients installed — restart hub to reload mounts"),
                _STATUS_TEXT_STYLE_RUNNING,
            )
        else:
            slicer.util.infoDisplay(
                _(
                    "SPA clients installed into:\n{hub}\n\n"
                    "Start the hub to serve them."
                ).format(hub=hub_path_str),
                windowTitle=_("Download SPA clients"),
            )
            self._set_status(
                _("SPA clients installed"),
                _STATUS_TEXT_STYLE_IDLE,
            )

    def _hub_script_path(self) -> str:
        return str(hub_script())

    def _is_running(self) -> bool:
        return self._hub_process is not None and self._hub_process.state() != qt.QProcess.NotRunning

    def _on_start(self) -> None:
        if self._is_running():
            return
        hub_path = str(hub_dir())
        script = self._hub_script_path()
        if not os.path.isfile(script):
            self._set_status(_("hub.py not found"), _STATUS_TEXT_STYLE_ERROR)
            return
        port = _hub_port_from_spin(self.portSpinBox)
        self._hub_port = port
        self._stopping = False
        try:
            _ensure_hub_deps()
        except HubDepsDeclinedError:
            self._set_status(
                _("Hub start cancelled (dependencies not installed)"),
                _STATUS_TEXT_STYLE_IDLE,
            )
            return
        except Exception as exc:
            self._set_status(
                _("Dependency install failed: {0}").format(exc),
                _STATUS_TEXT_STYLE_ERROR,
            )
            return

        jwt_secret = secrets.token_urlsafe(32)
        admin_token = secrets.token_urlsafe(24)
        cors_origins = (
            f"http://127.0.0.1:{port},http://localhost:{port}"
        )

        proc = qt.QProcess()
        proc.setProgram(sys.executable)
        # Loopback only: embedded Slicer hub must not listen on the LAN by default.
        proc.setArguments([script, "--host", "127.0.0.1", "--port", str(port)])
        proc.setWorkingDirectory(hub_path)
        env = qt.QProcessEnvironment.systemEnvironment()
        env.insert("HUB_AUTH_MODE", "mock")
        env.insert("HUB_JWT_SECRET", jwt_secret)
        env.insert("HUB_ADMIN_TOKEN", admin_token)
        env.insert("HUB_CORS_ORIGINS", cors_origins)
        proc.setProcessEnvironment(env)
        proc.setProcessChannelMode(qt.QProcess.MergedChannels)
        proc.readyReadStandardOutput.connect(self._on_hub_output)
        proc.finished.connect(self._on_hub_finished)
        proc.start()
        if not proc.waitForStarted(15000):
            self._set_status(_("Failed to start hub"), _STATUS_TEXT_STYLE_ERROR)
            proc.deleteLater()
            return

        self._hub_process = proc
        self._hub_pid = int(proc.processId())
        self._hub_jwt_secret = jwt_secret
        self._hub_admin_token = admin_token
        if self.startButton:
            self.startButton.enabled = False
        if self.stopButton:
            self.stopButton.enabled = True
        if self.openAdminButton:
            self.openAdminButton.enabled = True
        if self.portSpinBox:
            self.portSpinBox.enabled = False
        self._set_status(
            _("Running on port {0}").format(port),
            _STATUS_TEXT_STYLE_RUNNING,
        )

    def _reset_ui_stopped(self) -> None:
        if self.startButton:
            self.startButton.enabled = True
        if self.stopButton:
            self.stopButton.enabled = False
        if self.openAdminButton:
            self.openAdminButton.enabled = False
        if self.portSpinBox:
            self.portSpinBox.enabled = True

    def _stop_owned_hub(self) -> None:
        """Stop only the hub child process Slicer started (exit/cleanup)."""
        proc = self._hub_process
        if proc is not None:
            _force_stop_qprocess(proc)
            proc.deleteLater()
            self._hub_process = None
        elif self._hub_pid > 0 and _is_windows():
            _win_kill_process_tree(self._hub_pid)
        self._hub_pid = 0

    def _on_stop(self) -> None:
        port = self._hub_port or _hub_port_from_spin(self.portSpinBox)
        known_pid = self._hub_pid
        proc = self._hub_process
        self._stopping = True
        had_qprocess = proc is not None
        # Only stop the hub process tree Slicer started — never kill other
        # listeners that may have taken the port after the hub died.
        if proc is not None:
            _force_stop_qprocess(proc)
            proc.deleteLater()
            self._hub_process = None
        elif known_pid > 0 and _is_windows():
            _win_kill_process_tree(known_pid)
        self._hub_pid = 0
        self._hub_admin_token = ""
        self._hub_jwt_secret = ""
        self._reset_ui_stopped()
        if _port_is_listening("127.0.0.1", port):
            self._stopping = False
            self._set_status(
                _("Port {0} still in use — close other hub processes").format(port),
                _STATUS_TEXT_STYLE_ERROR,
            )
            return
        self._set_status(_("Hub stopped"), _STATUS_TEXT_STYLE_IDLE)
        # finished() clears _stopping when a QProcess was owned; otherwise clear now.
        if not had_qprocess:
            self._stopping = False

    def _on_open_admin(self) -> None:
        port = _hub_port_from_spin(self.portSpinBox)
        url = f"http://127.0.0.1:{port}/api/hub/admin"
        token = (self._hub_admin_token or "").strip()
        if token:
            # Fragment, not query: browsers never send it to the server or its logs.
            url = f"{url}#admin_token={quote(token, safe='')}"
        qt.QDesktopServices.openUrl(qt.QUrl(url))

    def _on_hub_output(self) -> None:
        if not self._hub_process:
            return
        raw = self._hub_process.readAllStandardOutput()
        data = raw.data().decode("utf-8", errors="replace")
        if data.strip():
            print(f"[Hub] {data.rstrip()}")

    def _on_hub_finished(
        self, exit_code: int, exit_status: Optional[qt.QProcess.ExitStatus] = None
    ) -> None:
        if exit_status is None:
            exit_status = (
                qt.QProcess.NormalExit
                if exit_code == 0
                else qt.QProcess.CrashExit
            )
        user_stopped = self._stopping
        self._stopping = False
        self._hub_process = None
        self._hub_pid = 0
        self._hub_admin_token = ""
        self._hub_jwt_secret = ""
        self._reset_ui_stopped()
        if user_stopped or (
            exit_status == qt.QProcess.NormalExit and exit_code == 0
        ):
            self._set_status(_("Hub stopped"), _STATUS_TEXT_STYLE_IDLE)
        else:
            self._set_status(
                _("Hub exited ({0})").format(exit_code),
                _STATUS_TEXT_STYLE_ERROR,
            )

    def cleanup(self) -> None:
        self._stop_owned_hub()

    def enter(self) -> None:
        pass

    def exit(self) -> None:
        # Match Slicer WebServer: leaving the module must not stop the process.
        # Hub stops only via Stop button or cleanup() (module unload).
        pass
