"""Enumerate local Slicer DICOM database studies for Hub slicerworklist / studyinfo."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger("WebSubInterface.ImageDisplay")

WORKLIST_ORG_3D_SLICER = "3d-slicer"
HUB_OPEN_MODE_LOCAL_DICOM = "local-dicom"
HUB_IDENTIFIER_DICOM_UID = "urn:dicom:uid"
HUB_OPEN_MODE = "open-mode"


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


def _instances_for_series(db: Any, series: Any) -> List[str]:
    try:
        instances = db.instancesForSeries(series) or []
    except Exception:
        return []
    out: List[str] = []
    for instance in instances:
        uid = str(instance or "").strip()
        if uid:
            out.append(uid)
    return out


def _dicom_database() -> Any:
    try:
        import slicer
    except Exception:
        return None
    return getattr(slicer, "dicomDatabase", None)


def list_local_dicom_worklist_studies() -> List[Dict[str, Any]]:
    """Return launchable study-level rows from ``slicer.dicomDatabase``.

    Single ``seriesForStudy`` pass per study (like WebServer ``handleStudies``),
    using ``instanceValue`` / ``instancesForSeries(..., 1)`` — no ``pydicom.dcmread``.
    """
    db = _dicom_database()
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
            patient_id = _instance_tag(db, representative, "0010,0020")
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
                    "patientName": patient_name,
                    "patientID": patient_id,
                    "studyDate": study_date,
                    "modalities": modalities,
                    "format": "DICOM",
                    "openMode": HUB_OPEN_MODE_LOCAL_DICOM,
                }
            )

    return studies


def build_local_dicom_imaging_study(study_instance_uid: str) -> Optional[Dict[str, Any]]:
    """Build a FHIR ImagingStudy resource for one study from ``slicer.dicomDatabase``.

    Uses ``instanceValue`` only (no ``pydicom.dcmread``). Returns ``None`` when the
    study cannot be resolved or has no series/instances.
    """
    study_uid = str(study_instance_uid or "").strip()
    if not study_uid:
        return None

    db = _dicom_database()
    if db is None:
        return None

    try:
        series_list = db.seriesForStudy(study_uid) or []
    except Exception as exc:
        LOGGER.warning(
            "dicomDatabase.seriesForStudy failed study=%s: %s", study_uid, exc
        )
        return None

    if not series_list:
        return None

    series_resources: List[Dict[str, Any]] = []
    modalities: List[str] = []
    total_instances = 0
    representative: Optional[str] = None

    for series in series_list:
        series_key = str(series or "").strip()
        if not series_key:
            continue
        instances = _instances_for_series(db, series_key)
        if not instances:
            continue

        first = instances[0]
        if representative is None:
            representative = first

        series_uid = _instance_tag(db, first, "0020,000E") or series_key
        modality = _instance_tag(db, first, "0008,0060") or "OT"
        if modality not in modalities:
            modalities.append(modality)
        series_number_raw = _instance_tag(db, first, "0020,0011")
        series_desc = _instance_tag(db, first, "0008,103E")

        instance_resources: List[Dict[str, Any]] = []
        for index, instance_uid in enumerate(instances):
            sop_uid = _instance_tag(db, instance_uid, "0008,0018") or instance_uid
            sop_class = _instance_tag(db, instance_uid, "0008,0016")
            instance_number_raw = _instance_tag(db, instance_uid, "0020,0013")
            try:
                instance_number = int(instance_number_raw) if instance_number_raw else index + 1
            except ValueError:
                instance_number = index + 1
            entry: Dict[str, Any] = {
                "uid": sop_uid,
                "number": instance_number,
            }
            if sop_class:
                entry["sopClass"] = {"code": sop_class}
            instance_resources.append(entry)

        total_instances += len(instance_resources)
        series_entry: Dict[str, Any] = {
            "uid": series_uid,
            "modality": {
                "coding": [{"system": "http://dicom.nema.org/resources/ontology/DCM", "code": modality}]
            },
            "numberOfInstances": len(instance_resources),
            "instance": instance_resources,
        }
        if series_number_raw:
            try:
                series_entry["number"] = int(series_number_raw)
            except ValueError:
                pass
        if series_desc:
            series_entry["description"] = series_desc
        series_resources.append(series_entry)

    if not series_resources or representative is None:
        return None

    resolved_study_uid = _instance_tag(db, representative, "0020,000D") or study_uid
    patient_name = _instance_tag(db, representative, "0010,0010") or "Unknown"
    patient_id = _instance_tag(db, representative, "0010,0020")
    study_desc = _instance_tag(db, representative, "0008,1030")
    study_date = _instance_tag(db, representative, "0008,0020")
    study_id = f"slicer-dicom:{resolved_study_uid}"

    subject: Dict[str, Any] = {"display": patient_name}
    if patient_id:
        subject["identifier"] = [{"value": patient_id}]

    resource: Dict[str, Any] = {
        "resourceType": "ImagingStudy",
        "id": study_id,
        "status": "available",
        "uid": resolved_study_uid,
        "numberOfSeries": len(series_resources),
        "numberOfInstances": total_instances,
        "subject": subject,
        "identifier": [
            {"system": HUB_IDENTIFIER_DICOM_UID, "value": resolved_study_uid},
            {"system": HUB_OPEN_MODE, "value": HUB_OPEN_MODE_LOCAL_DICOM},
        ],
        "series": series_resources,
    }
    if study_date:
        resource["started"] = study_date
    if study_desc:
        resource["description"] = study_desc
    if modalities:
        resource["modality"] = [{"code": code} for code in modalities]

    return resource
