"""3D Slicer scripted module: Slicer WebSub."""

from __future__ import annotations

from Lib.repo_paths import ensure_monorepo_import_paths

ensure_monorepo_import_paths()

import ctk

from slicer.i18n import tr as _
from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleWidget,
)

from Lib.HubServer import HubServerWidget
from Lib.ImageDisplayClient import ImageDisplayClientWidget


class WebSubInterface(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("WebSub server")
        self.parent.categories = [_("Informatics")]
        self.parent.dependencies = []
        self.parent.contributors = ["Martin Bellehumeur"]
        self.parent.helpText = _(
            """
            This module connects 3D Slicer to a Slicer WebSub hub and can start a local hub.
            Full product documentation:
            <a href="https://github.com/mbellehumeur/SlicerWebSub">SlicerWebSub README</a>.<br><br>
            <b>Image Display Client</b><br>
            Choose a hub preset (for example local <code>SLICER-HUB</code> or a cloud hub), set the
            topic under <b>User</b>, optionally enable <b>OIDC</b> for browser login, then
            <b>Connect</b>. Use <b>Open</b> for the hub admin portal.
            <b>Open worklist</b> opens the worklist client for the selected hub.
            After connect, <b>Start a conference</b> creates or manages a collaborative
            session.<br><br>
            <b>Hub</b><br>
            Expand the Hub section to run a hub inside Slicer: set the <b>Port</b>,
            <b>Start</b> / <b>Stop</b> the process, and <b>Open Hub Portal</b> when it is running.
            Point the Image Display Client at the same hub to subscribe as an image display.
            """
        )
        self.parent.acknowledgementText = _(
            """
            <b>License</b><br>
            Slicer WebSub is distributed under the
            <a href="https://github.com/mbellehumeur/SlicerWebSub/blob/main/LICENSE.txt">MIT License</a>.<br><br>
            <b>Acknowledgements</b><br>
            <b>3D Slicer</b> &mdash; open-source platform for medical image computing from the
            <a href="https://www.slicer.org/">3D Slicer community</a>.
            This extension is built for and distributed through the 3D Slicer extension ecosystem.<br><br>
            <b>TotalSegmentator</b> was created by the Department of Research and Analysis at University Hospital Basel.
            If you use it, please cite our Radiology: Artificial Intelligence paper
            (<a href="https://arxiv.org/abs/2208.05868">free preprint</a>).
            If you use it for MR images, please cite the TotalSegmentator MRI <i>Radiology</i> paper
            (<a href="https://arxiv.org/abs/2405.19492">free preprint</a>).<br><br>
            <b>nnU-Net</b> &mdash; TotalSegmentator is heavily based on nnU-Net
            (<a href="https://arxiv.org/abs/1809.10486">preprint</a>).<br><br>
            <b>IDC Claude</b> &mdash; builds custom worklists from natural-language queries against the
            <a href="https://portal.imaging.datacommons.cancer.gov/">Imaging Data Commons</a>
            (National Cancer Institute) using Anthropic Claude. Query guidance follows the
            <a href="https://github.com/ImagingDataCommons/imaging-data-commons-skill">IDC skill</a>.<br><br>
            <b>idc-index</b> &mdash; official
            <a href="https://github.com/ImagingDataCommons/idc-index">Imaging Data Commons</a>
            Python package for local DuckDB SQL against IDC metadata and DICOM series download URLs;
            used by the IDC Claude service provider. If you use it in research, cite Fedorov A, et al.,
            <i>Radiographics</i> (<a href="https://doi.org/10.1148/rg.230180">2023</a>).<br><br>
            <b>OsiriX</b> &mdash; DICOM image processing software from
            <a href="https://www.osirix-viewer.com/">Pixmeo SARL</a>.<br><br>
            <b>OHIF</b> &mdash; open-source zero-footprint viewer from the
            <a href="https://ohif.org/">Open Health Imaging Foundation</a>.<br><br>
            <b>Slim</b> &mdash; interoperable slide microscopy viewer from the
            <a href="https://github.com/ImagingDataCommons/slim">Imaging Data Commons</a>
            (National Cancer Institute).<br><br>
            <b>SlicerLive</b> &mdash; experimental WebGPU live 3D Slicer scenes in the browser from
            <a href="https://github.com/pieper/SlicerLive/">SlicerLive</a>;
            used for IRA / hub-mirror demos served from the hub.<br><br>
            <b>Standards and trademarks</b><br>
            DICOM&reg; is the registered trademark of the National Electrical Manufacturers Association (NEMA)
            for its standards publications relating to digital imaging and communications in medicine.
            FHIR&reg; and related HL7 marks are registered trademarks of Health Level Seven International (HL7).
            IHE&reg; is a registered trademark of HIMSS. OsiriX&reg; is a trademark of Pixmeo SARL.
            OHIF&reg; is a trademark of the Open Health Imaging Foundation.
            Imaging Data Commons&reg; is a trademark of the National Cancer Institute.<br><br>
            The Slicer WebSub (including its hub, clients, and documentation) references ideas, workflows, and vocabulary
            drawn from these standards&mdash;such as DICOM objects and metadata, FHIR and FHIRcast-style context and events,
            and IHE actor roles (for example, Image Display and Evidence Creator)&mdash;and product names such as OsiriX,
            OHIF, and Imaging Data Commons solely to describe interoperability behavior.<br><br>
            <b>Slicer WebSub is not part of these standards.</b>
            It is not published by NEMA, HL7, or HIMSS, and is not an IHE Integration Profile, a FHIR implementation guide,
            or a DICOM conformance statement. Use of standard names and terms does not imply endorsement, certification,
            or official status. All other product and company names are trademarks of their respective owners.
            """
        )


class WebSubInterfaceWidget(ScriptedLoadableModuleWidget):
    def __init__(self, parent=None) -> None:
        ScriptedLoadableModuleWidget.__init__(self, parent)
        self.imageDisplayClientWidget = ImageDisplayClientWidget()
        self.hubWidget = HubServerWidget()

    @staticmethod
    def _ctk_collapsible_section(title: str, *, expanded: bool = True):
        section = ctk.ctkCollapsibleButton()
        section.text = title
        section.collapsed = not expanded
        return section

    def setup(self) -> None:
        ScriptedLoadableModuleWidget.setup(self)
        self.layout.setSpacing(10)

        clientSection = self._ctk_collapsible_section(
            _("Image Display Client"), expanded=True
        )
        self.layout.addWidget(clientSection)
        self.imageDisplayClientWidget.setup(clientSection)

        hubSection = self._ctk_collapsible_section(_("Hub"), expanded=False)
        self.layout.addWidget(hubSection)
        self.hubWidget.setup(hubSection)

        self.layout.addStretch(1)

    def cleanup(self) -> None:
        self.imageDisplayClientWidget.cleanup()
        self.hubWidget.cleanup()

    def enter(self) -> None:
        self.imageDisplayClientWidget.enter()
        self.hubWidget.enter()

    def exit(self) -> None:
        self.imageDisplayClientWidget.exit()
        self.hubWidget.exit()
