"""Enumerate local Slicer DICOM database studies for Hub STATUS worklist."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger("WebSubInterface.ImageDisplay")

WORKLIST_ORG_3D_SLICER = "3d-slicer"
HUB_OPEN_MODE_LOCAL_DICOM = "local-dicom"


def _instance_tag(db: Any, instance: str, tag: str) -> str:
    try:
        value = db.instanceValue(instance, tag)
    except Exception:
        return ""
    return str(value or "").strip()


def _first_instance_uid(db: Any, series: Any) -> str:
    """Return the first instance UID for a series (prefer limited DB query)."""
    try:
        instances = db.instancesForSeries(series, 1) or []
    except TypeError:
        try:
            instances = db.instancesForSeries(series) or []
        except Exception:
            return ""
    except Exception:
        return ""
    if not instances:
        return ""
    return str(instances[0] or "").strip()


def list_local_dicom_worklist_studies() -> List[Dict[str, Any]]:
    """Return launchable study rows from ``slicer.dicomDatabase`` (WebServer QIDO-style).

    Single ``seriesForStudy`` pass per study (like WebServer ``handleStudies``),
    using ``instanceValue`` / ``instancesForSeries(..., 1)`` — no ``pydicom.dcmread``.
    """
    try:
        import slicer
    except Exception:
        return []

    db = getattr(slicer, "dicomDatabase", None)
    if db is None:
        return []

    try:
        patients = db.patients() or []
    except Exception as exc:
        LOGGER.warning("dicomDatabase.patients failed: %s", exc)
        return []

    studies: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for patient in patients:
        try:
            study_uids = db.studiesForPatient(patient) or []
        except Exception:
            continue
        for study in study_uids:
            study_key = str(study or "").strip()
            if not study_key or study_key in seen:
                continue

            try:
                series_list = db.seriesForStudy(study_key) or []
            except Exception:
                continue

            representative: Optional[str] = None
            modalities: List[str] = []
            for series in series_list:
                instance = _first_instance_uid(db, series)
                if not instance:
                    continue
                if representative is None:
                    representative = instance
                modality = _instance_tag(db, instance, "0008,0060")
                if modality and modality not in modalities:
                    modalities.append(modality)

            if not representative:
                continue

            study_uid = _instance_tag(db, representative, "0020,000D") or study_key
            if study_uid in seen:
                continue
            seen.add(study_uid)
            seen.add(study_key)

            patient_name = _instance_tag(db, representative, "0010,0010") or "Unknown"
            study_desc = _instance_tag(db, representative, "0008,1030")
            study_date = _instance_tag(db, representative, "0008,0020")
            if not modalities:
                modalities = ["OT"]

            name = patient_name
            if study_desc:
                name = f"{patient_name} — {study_desc}"
            elif study_date:
                name = f"{patient_name} — {study_date}"

            studies.append(
                {
                    "id": f"slicer-dicom:{study_uid}",
                    "name": name,
                    "description": study_desc or study_date or "",
                    "organization": WORKLIST_ORG_3D_SLICER,
                    "studyInstanceUID": study_uid,
                    "modalities": modalities,
                    "format": "DICOM",
                    "openMode": HUB_OPEN_MODE_LOCAL_DICOM,
                }
            )

    return studies
