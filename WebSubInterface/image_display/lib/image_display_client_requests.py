"""Image Display Client Hub request handlers (status / slicerworklist / studyinfo / …)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, TYPE_CHECKING

from hub_client import (
    data_type_from_event_name,
    hub_event_name,
    is_request_event,
    normalize_data_type,
    request_context,
)

if TYPE_CHECKING:
    from hub_client import SlicerHubClient
    from image_display_client_hub import ImageDisplayClientConnection

LOGGER = logging.getLogger("WebSubInterface.ImageDisplay")

_DEFAULT_DISPLAY_PRODUCT_NAME = "3DSLICER-ID"

EMPTY_FHIRCAST_CONTEXT: Dict[str, Any] = {"context.type": "", "context": []}
ID_ACTOR_KEYWORD = "ID"
STATUS_DATA_TYPE = "status"
LIVESCENE_DATA_TYPE = "livescene"
DICOM_DATA_TYPE = "dicom"
SLICERWORKLIST_DATA_TYPE = "slicerworklist"
SLICERSTUDYINFO_DATA_TYPE = "slicerstudyinfo"
# STATUS must finish inside the hub's default ~2s request fan-out so worklist
# presence (and second-tab probes) see 3DSLICER-ID. Viewport Qt grab()/PNG encode
# was the slow path; STATUS uses placeholders instead.
#
# TODO(later): optional rich STATUS / sceneview path that restores real viewport
# grabs (capture_viewport_thumbnail_png) under an explicit longer timeoutSeconds,
# without blocking the fast presence reply.
STATUS_BUILD_TIMEOUT_SECONDS = 1.5
LIVESCENE_EXPORT_TIMEOUT_SECONDS = 120.0
DICOM_EXPORT_TIMEOUT_SECONDS = 300.0
SLICERWORKLIST_TIMEOUT_SECONDS = 5.0
SLICERSTUDYINFO_TIMEOUT_SECONDS = 10.0


def _normalize_target_actor(value: Any) -> str:
    if isinstance(value, str):
        return value.strip().upper()
    return ""


def _accepts_inbound_target(message: Dict[str, Any]) -> bool:
    target = message.get("target.actor")
    if target is None:
        return True
    keyword = _normalize_target_actor(target)
    if not keyword or keyword == "*":
        return True
    return keyword == ID_ACTOR_KEYWORD


def _accepts_target_product(message: Dict[str, Any], product_name: str) -> bool:
    target_product = message.get("target.product.name")
    if target_product is None:
        return True
    text = str(target_product).strip()
    if not text or text == "*":
        return True
    expected = (product_name or _DEFAULT_DISPLAY_PRODUCT_NAME).strip()
    return text.upper() == expected.upper()


def _request_correlation_id(message: Dict[str, Any]) -> str:
    context = request_context(message)
    correlation_id = context.get("id")
    if isinstance(correlation_id, str) and correlation_id.strip():
        return correlation_id.strip()
    return ""


def _request_data_type(message: Dict[str, Any], hub_event: str) -> str:
    context = request_context(message)
    data_type = context.get("dataType")
    if isinstance(data_type, str) and data_type.strip():
        return data_type.strip()
    return data_type_from_event_name(hub_event)


def _resolve_product_name(connection: "ImageDisplayClientConnection") -> str:
    name = (connection.get_product_name() or "").strip()
    if name:
        return name
    client = connection.get_client()
    if client is not None:
        session_name = client.product_name
        if session_name:
            return session_name
    return _DEFAULT_DISPLAY_PRODUCT_NAME


def _topic_from_message(message: Dict[str, Any]) -> Any:
    event = message.get("event") or {}
    return event.get("hub.topic")


def _open_context_fields(open_context: List[Any]) -> Dict[str, Any]:
    context = list(open_context or [])
    if context:
        return {"context.type": "ImagingStudy", "context": context}
    return dict(EMPTY_FHIRCAST_CONTEXT)


async def handle_status_request(
    connection: "ImageDisplayClientConnection",
    client: "SlicerHubClient",
    message: Dict[str, Any],
) -> None:
    correlation_id = _request_correlation_id(message)
    if not correlation_id:
        LOGGER.info("Ignoring status-request: missing context.id")
        return

    product_name = _resolve_product_name(connection)
    open_context = connection.get_last_open_context()

    def build_status_payload() -> Dict[str, Any]:
        from build_sceneview_response import build_sceneview_response_payload

        # Skip viewport grab() — placeholders only (see STATUS_BUILD_TIMEOUT note).
        sceneview = build_sceneview_response_payload(
            product_name,
            open_context,
            fast_placeholder_thumbnails=True,
        )
        payload: Dict[str, Any] = {
            "source": "status",
            "product": product_name,
            "sceneview": sceneview,
        }
        payload.update(_open_context_fields(open_context))
        return payload

    try:
        payload = await asyncio.wait_for(
            connection.run_on_main_thread(build_status_payload),
            timeout=STATUS_BUILD_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        LOGGER.error(
            "status build timed out after %.1fs; sending minimal context+sceneview payload",
            STATUS_BUILD_TIMEOUT_SECONDS,
        )
        payload = {
            "source": "status",
            "product": product_name,
            "sceneview": {
                "source": "sceneview",
                "product": product_name,
                "window": {},
                "display": {},
                "viewports": [],
            },
        }
        payload.update(_open_context_fields(open_context))

    client.send_hub_request_response(
        correlation_id,
        STATUS_DATA_TYPE,
        payload,
        _topic_from_message(message),
    )
    sceneview = payload.get("sceneview") if isinstance(payload, dict) else {}
    viewports = sceneview.get("viewports") if isinstance(sceneview, dict) else []
    LOGGER.info(
        "sent status-response id=%s viewportCount=%d contextType=%s",
        correlation_id,
        len(viewports) if isinstance(viewports, list) else 0,
        payload.get("context.type") if isinstance(payload, dict) else "",
    )


async def handle_slicerworklist_request(
    connection: "ImageDisplayClientConnection",
    client: "SlicerHubClient",
    message: Dict[str, Any],
) -> None:
    """Return study-level rows from the local DICOM database."""
    correlation_id = _request_correlation_id(message)
    if not correlation_id:
        LOGGER.info("Ignoring slicerworklist-request: missing context.id")
        return

    product_name = _resolve_product_name(connection)

    def build_payload() -> Dict[str, Any]:
        from local_dicom_worklist import list_local_dicom_worklist_studies

        return {
            "source": "slicerworklist",
            "product": product_name,
            "studies": list_local_dicom_worklist_studies(),
        }

    try:
        payload = await asyncio.wait_for(
            connection.run_on_main_thread(build_payload),
            timeout=SLICERWORKLIST_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        LOGGER.warning("slicerworklist-request failed: %s", exc)
        payload = {
            "source": "slicerworklist",
            "product": product_name,
            "ok": False,
            "error": str(exc).strip() or exc.__class__.__name__,
            "studies": [],
        }

    client.send_hub_request_response(
        correlation_id,
        SLICERWORKLIST_DATA_TYPE,
        payload,
        _topic_from_message(message),
    )
    studies = payload.get("studies") if isinstance(payload, dict) else []
    LOGGER.info(
        "sent slicerworklist-response id=%s studyCount=%d",
        correlation_id,
        len(studies) if isinstance(studies, list) else 0,
    )


async def handle_slicerstudyinfo_request(
    connection: "ImageDisplayClientConnection",
    client: "SlicerHubClient",
    message: Dict[str, Any],
) -> None:
    """Return a full ImagingStudy for one StudyInstanceUID from the local DICOM DB."""
    correlation_id = _request_correlation_id(message)
    if not correlation_id:
        LOGGER.info("Ignoring slicerstudyinfo-request: missing context.id")
        return

    product_name = _resolve_product_name(connection)
    context = request_context(message)
    study_uid = str(context.get("studyInstanceUID") or "").strip()

    def build_payload() -> Dict[str, Any]:
        from local_dicom_worklist import build_local_dicom_imaging_study

        if not study_uid:
            return {
                "source": "slicerstudyinfo",
                "product": product_name,
                "ok": False,
                "error": "studyInstanceUID required",
                "context.type": "",
                "context": [],
            }
        resource = build_local_dicom_imaging_study(study_uid)
        if resource is None:
            return {
                "source": "slicerstudyinfo",
                "product": product_name,
                "ok": False,
                "error": f"study not found: {study_uid}",
                "context.type": "",
                "context": [],
                "studyInstanceUID": study_uid,
            }
        return {
            "source": "slicerstudyinfo",
            "product": product_name,
            "ok": True,
            "context.type": "ImagingStudy",
            "context": [{"key": "study", "resource": resource}],
            "studyInstanceUID": str(resource.get("uid") or study_uid),
        }

    try:
        payload = await asyncio.wait_for(
            connection.run_on_main_thread(build_payload),
            timeout=SLICERSTUDYINFO_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        LOGGER.warning("slicerstudyinfo-request failed: %s", exc)
        payload = {
            "source": "slicerstudyinfo",
            "product": product_name,
            "ok": False,
            "error": str(exc).strip() or exc.__class__.__name__,
            "context.type": "",
            "context": [],
            "studyInstanceUID": study_uid,
        }

    client.send_hub_request_response(
        correlation_id,
        SLICERSTUDYINFO_DATA_TYPE,
        payload,
        _topic_from_message(message),
    )
    LOGGER.info(
        "sent slicerstudyinfo-response id=%s study=%s ok=%s",
        correlation_id,
        study_uid,
        payload.get("ok") if isinstance(payload, dict) else None,
    )


async def handle_hub_request(
    connection: "ImageDisplayClientConnection",
    client: "SlicerHubClient",
    message: Dict[str, Any],
) -> None:
    hub_event = hub_event_name(message)
    if not is_request_event(hub_event):
        return

    if not _accepts_inbound_target(message):
        LOGGER.info(
            "Ignoring %s: target actor mismatch (%s)",
            hub_event,
            message.get("target.actor"),
        )
        return

    product_name = _resolve_product_name(connection)
    if not _accepts_target_product(message, product_name):
        LOGGER.info(
            "Ignoring %s: target product mismatch (%s)",
            hub_event,
            message.get("target.product.name"),
        )
        return

    data_type = _request_data_type(message, hub_event)
    normalized = normalize_data_type(data_type)

    if normalized == normalize_data_type(STATUS_DATA_TYPE):
        await handle_status_request(connection, client, message)
        return

    if normalized == normalize_data_type(SLICERWORKLIST_DATA_TYPE):
        await handle_slicerworklist_request(connection, client, message)
        return

    if normalized == normalize_data_type(SLICERSTUDYINFO_DATA_TYPE):
        await handle_slicerstudyinfo_request(connection, client, message)
        return

    if normalized == normalize_data_type(LIVESCENE_DATA_TYPE):
        await handle_livescene_request(connection, client, message)
        return

    if normalized == normalize_data_type(DICOM_DATA_TYPE):
        await handle_dicom_request(connection, client, message)
        return

    LOGGER.debug(
        "Ignoring unsupported request event=%s dataType=%s",
        hub_event,
        data_type,
    )


async def handle_livescene_request(
    connection: "ImageDisplayClientConnection",
    client: "SlicerHubClient",
    message: Dict[str, Any],
) -> None:
    """Export current MRML LiveScene and publish ImagingStudy-open (multipart blobs)."""
    correlation_id = _request_correlation_id(message)
    topic = _topic_from_message(message) or connection.get_topic() or ""

    def export_on_main() -> tuple:
        from live_scene_export import (
            build_livescene_imaging_study_open_message,
            export_live_scene_document,
        )

        scene_doc, blob_parts = export_live_scene_document()
        msg = build_livescene_imaging_study_open_message(
            topic=str(topic or ""),
            scene_doc=scene_doc,
            blob_parts=blob_parts,
        )
        return msg, len(scene_doc.get("nodes") or {}), len(blob_parts)

    try:
        hub_message, node_count, blob_count = await asyncio.wait_for(
            connection.run_on_main_thread(export_on_main),
            timeout=LIVESCENE_EXPORT_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        LOGGER.warning("LiveScene export failed: %s", exc)
        if correlation_id:
            client.send_hub_request_response(
                correlation_id,
                LIVESCENE_DATA_TYPE,
                {
                    "source": "livescene",
                    "ok": False,
                    "error": str(exc).strip() or exc.__class__.__name__,
                },
                _topic_from_message(message),
            )
        return

    status = await client.publish(hub_message)
    LOGGER.info(
        "livescene-request: published ImagingStudy-open nodes=%d blobs=%d http=%s",
        node_count,
        blob_count,
        status,
    )
    if correlation_id:
        client.send_hub_request_response(
            correlation_id,
            LIVESCENE_DATA_TYPE,
            {
                "source": "livescene",
                "ok": True,
                "product": _resolve_product_name(connection),
                "nodeCount": node_count,
                "blobCount": blob_count,
            },
            _topic_from_message(message),
        )


def _dicom_request_uids(message: Dict[str, Any]) -> tuple[str, str]:
    context = request_context(message)
    study_uid = str(context.get("studyInstanceUID") or "").strip()
    series_uid = str(context.get("seriesInstanceUID") or "").strip()
    return study_uid, series_uid


async def handle_dicom_request(
    connection: "ImageDisplayClientConnection",
    client: "SlicerHubClient",
    message: Dict[str, Any],
) -> None:
    """Export local DICOM DB files and publish dicom-send for web viewers."""
    correlation_id = _request_correlation_id(message)
    topic = _topic_from_message(message) or connection.get_topic() or ""
    study_uid, series_uid = _dicom_request_uids(message)

    def export_on_main() -> tuple:
        from local_dicom_export import export_local_dicom_send_message

        return export_local_dicom_send_message(
            topic=str(topic or ""),
            study_instance_uid=study_uid,
            series_instance_uid=series_uid,
        )

    try:
        hub_message, resolved_study_uid, file_count = await asyncio.wait_for(
            connection.run_on_main_thread(export_on_main),
            timeout=DICOM_EXPORT_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        LOGGER.warning("dicom-request export failed: %s", exc)
        if correlation_id:
            client.send_hub_request_response(
                correlation_id,
                DICOM_DATA_TYPE,
                {
                    "source": "dicom",
                    "ok": False,
                    "error": str(exc).strip() or exc.__class__.__name__,
                    "studyInstanceUID": study_uid,
                },
                _topic_from_message(message),
            )
        return

    status = await client.publish(hub_message)
    LOGGER.info(
        "dicom-request: published dicom-send study=%s files=%d http=%s",
        resolved_study_uid,
        file_count,
        status,
    )
    if correlation_id:
        client.send_hub_request_response(
            correlation_id,
            DICOM_DATA_TYPE,
            {
                "source": "dicom",
                "ok": True,
                "product": _resolve_product_name(connection),
                "fileCount": file_count,
                "studyInstanceUID": resolved_study_uid,
            },
            _topic_from_message(message),
        )
