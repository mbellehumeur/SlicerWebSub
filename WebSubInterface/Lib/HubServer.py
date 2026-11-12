"""Slicer WebSub — Hub subsection (embedded Slicer hub server UI)."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from typing import List, Optional

import qt

from slicer.i18n import tr as _
import slicer

DEFAULT_HUB_PORT = 2018

_STATUS_TEXT_STYLE_IDLE = "color: palette(text);"
_STATUS_TEXT_STYLE_RUNNING = "color: palette(link);"
_STATUS_TEXT_STYLE_ERROR = "color: palette(negative);"

from .repo_paths import hub_dir, hub_script, repo_root
from .spa_download import (
    SPA_DOWNLOAD_CATALOG,
    default_checked,
    download_and_extract,
    is_installed,
)


# pip spec -> import name (Slicer pip_install accepts one package per call).
_HUB_PIP_PACKAGES = (
    ("fastapi", "fastapi"),
    ("uvicorn[standard]", "uvicorn"),
    ("python-multipart", "multipart"),
    ("aiohttp", "aiohttp"),
    ("psutil", "psutil"),
)


class HubDepsDeclinedError(RuntimeError):
    """User declined installing missing hub packages into Slicer Python."""


def _ensure_hub_deps() -> None:
    """Install hub deps via Slicer pip (one package per call) after confirm."""
    missing = []
    for pip_spec, import_name in _HUB_PIP_PACKAGES:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_spec)
    if not missing:
        return
    package_list = "\n".join(f"  • {spec}" for spec in missing)
    if not slicer.util.confirmYesNoDisplay(
        _(
            "The hub needs packages that are not installed in this Slicer "
            "Python environment:\n\n{packages}\n\n"
            "Install them now with pip? This changes the Slicer Python site-packages."
        ).format(packages=package_list),
        windowTitle=_("Install hub dependencies"),
    ):
        raise HubDepsDeclinedError("dependency install declined")
    for pip_spec in missing:
        slicer.util.pip_install(pip_spec)
    import importlib

    for _pip_spec, import_name in _HUB_PIP_PACKAGES:
        importlib.import_module(import_name)


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

        self.portSpinBox: Optional[qt.QSpinBox] = None
        self.startButton: Optional[qt.QPushButton] = None
        self.stopButton: Optional[qt.QPushButton] = None
        self.openAdminButton: Optional[qt.QPushButton] = None
        self.downloadSpasButton: Optional[qt.QPushButton] = None
        self.statusLabel: Optional[qt.QLabel] = None
        self._spa_checkboxes: dict = {}

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

        spa_panel = qt.QWidget()
        spa_layout = qt.QVBoxLayout(spa_panel)
        spa_layout.setContentsMargins(0, 0, 0, 0)
        spa_layout.setSpacing(2)
        spa_grid = qt.QWidget()
        spa_grid_layout = qt.QGridLayout(spa_grid)
        spa_grid_layout.setContentsMargins(0, 0, 0, 0)
        spa_grid_layout.setHorizontalSpacing(12)
        spa_grid_layout.setVerticalSpacing(2)
        self._spa_checkboxes = {}
        columns = 3
        for index, entry in enumerate(SPA_DOWNLOAD_CATALOG):
            checkbox = qt.QCheckBox(entry.label)
            checkbox.setProperty("spaFolder", entry.folder)
            self._spa_checkboxes[entry.folder] = checkbox
            spa_grid_layout.addWidget(checkbox, index // columns, index % columns)
        spa_layout.addWidget(spa_grid)
        self.downloadSpasButton = qt.QPushButton(_("Download SPAs"))
        self.downloadSpasButton.setToolTip(
            _(
                "Download selected browser clients from GitHub into the local "
                "hub folder (worklist, OHIF, …)"
            )
        )
        spa_layout.addWidget(self.downloadSpasButton)
        layout.addRow(_("SPAs:"), spa_panel)
        self._refresh_spa_checkboxes()

        self.startButton.connect("clicked()", self._on_start)
        self.stopButton.connect("clicked()", self._on_stop)
        self.openAdminButton.connect("clicked()", self._on_open_admin)
        self.downloadSpasButton.connect("clicked()", self._on_download_spas)

    def _set_status(self, text: str, style: str = _STATUS_TEXT_STYLE_IDLE) -> None:
        if self.statusLabel:
            self.statusLabel.setText(text)
            self.statusLabel.setStyleSheet(style)

    def _refresh_spa_checkboxes(self) -> None:
        root = hub_dir()
        for entry in SPA_DOWNLOAD_CATALOG:
            checkbox = self._spa_checkboxes.get(entry.folder)
            if not checkbox:
                continue
            installed = is_installed(root, entry.folder)
            checkbox.setChecked(default_checked(entry.folder, installed))
            if installed:
                checkbox.setToolTip(
                    _("Already installed — check to re-download and overwrite")
                )
            else:
                checkbox.setToolTip(
                    _("Not installed — download from GitHub release {tag}").format(
                        tag="spa-clients"
                    )
                )

    def _on_download_spas(self) -> None:
        selected = [
            folder
            for folder, checkbox in self._spa_checkboxes.items()
            if checkbox and checkbox.isChecked()
        ]
        if not selected:
            self._set_status(
                _("Select at least one SPA to download"),
                _STATUS_TEXT_STYLE_IDLE,
            )
            return

        root = hub_dir()
        overwrite = [f for f in selected if is_installed(root, f)]
        if overwrite:
            names = ", ".join(overwrite)
            if not slicer.util.confirmYesNoDisplay(
                _(
                    "These SPAs are already installed and will be overwritten:\n\n"
                    "{names}\n\nContinue?"
                ).format(names=names),
                windowTitle=_("Overwrite SPA clients"),
            ):
                return

        if self.downloadSpasButton:
            self.downloadSpasButton.enabled = False
        ok_folders: List[str] = []
        errors: List[str] = []
        try:
            for folder in selected:
                label = next(
                    (e.label for e in SPA_DOWNLOAD_CATALOG if e.folder == folder),
                    folder,
                )
                self._set_status(
                    _("Downloading {name}…").format(name=label),
                    _STATUS_TEXT_STYLE_RUNNING,
                )
                slicer.app.processEvents()
                try:
                    download_and_extract(
                        root,
                        folder,
                        overwrite=True,
                    )
                    ok_folders.append(folder)
                except Exception as exc:
                    errors.append(f"{label}: {exc}")
        finally:
            if self.downloadSpasButton:
                self.downloadSpasButton.enabled = True
            self._refresh_spa_checkboxes()

        if errors and not ok_folders:
            self._set_status(
                _("SPA download failed: {0}").format(errors[0]),
                _STATUS_TEXT_STYLE_ERROR,
            )
            return
        if errors:
            self._set_status(
                _("Downloaded {n}; errors: {err}").format(
                    n=len(ok_folders), err=errors[0]
                ),
                _STATUS_TEXT_STYLE_ERROR,
            )
        else:
            self._set_status(
                _("Downloaded {n} SPA(s)").format(n=len(ok_folders)),
                _STATUS_TEXT_STYLE_RUNNING
                if self._is_running()
                else _STATUS_TEXT_STYLE_IDLE,
            )

        if ok_folders and self._is_running():
            if slicer.util.confirmYesNoDisplay(
                _(
                    "SPA clients were installed, but the hub must restart to "
                    "serve them. Stop and start the hub now?"
                ),
                windowTitle=_("Restart hub"),
            ):
                self._on_stop()
                if not _port_is_listening("127.0.0.1", self._hub_port):
                    self._on_start()

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

        proc = qt.QProcess()
        proc.setProgram(sys.executable)
        proc.setArguments([script, "--port", str(port)])
        proc.setWorkingDirectory(hub_path)
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
        qt.QDesktopServices.openUrl(qt.QUrl(f"http://127.0.0.1:{port}/api/hub/admin"))

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
