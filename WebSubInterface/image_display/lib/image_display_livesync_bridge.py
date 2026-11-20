"""Bridge LiveSync mrson wire messages over Hub scene-update.

When slicer-mirror sends ``{ op: subscribe, ... }`` via scene-update, Image Display:
1. Uploads blob chunks as multipart **scene-update** (HubBlobs + context.files[])
2. Publishes **Snapshot** scene-update with the LiveScene document (first paint)
3. Optionally attaches a Hub sink peer for live MRML events (when ModuleServer is up)

A ``metadataOnly`` subscribe (e.g. IRA following camera / slices / segmentation display)
skips 1., gets a bulk-free Snapshot addressed to it alone, and joins the shared sink.

Subscribers are tracked per ``subscriber.name``; the sink streams their combined request.
``{ op: unsubscribe }`` (and idle timeout) drops that subscriber; the Hub sink detaches when
none remain. applyOps / reconcile are forwarded when the sink is up.
Image Display LiveSync path publishes **only** scene-update (no ImagingStudy-open).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from image_display_client_hub import ImageDisplayClientConnection

LOGGER = logging.getLogger("WebSubInterface.ImageDisplay")

LIVESYNC_CONTEXT_KEY = "livesync"
LIVESYNC_EXPORT_TIMEOUT_SECONDS = 120.0
# Detach Hub sink if no inbound LiveSync ops arrive (covers tab kill without unsubscribe).
LIVESYNC_IDLE_DETACH_SECONDS = 180.0
HUB_BLOBS_EVENT = "HubBlobs"
SNAPSHOT_EVENT = "Snapshot"


def _mark_livesync_inbound(connection: "ImageDisplayClientConnection") -> None:
    connection._livesync_last_inbound = time.monotonic()
    connection._livesync_armed = True


def _clear_livesync_armed(connection: "ImageDisplayClientConnection") -> None:
    connection._livesync_armed = False
    connection._livesync_last_inbound = 0.0


async def detach_livesync_hub_sink(
    connection: "ImageDisplayClientConnection",
    *,
    reason: str,
) -> None:
    """Tear down ModuleServer Hub sink observers (stop scene-update flood)."""
    bridge = getattr(connection, "_mrson_hub_bridge", None)
    if bridge is None:
        _clear_livesync_armed(connection)
        return

    def run() -> None:
        bridge.detach()

    try:
        await connection.run_on_main_thread(run)
        LOGGER.info("livesync Hub sink detached reason=%s", reason)
    except Exception as exc:
        LOGGER.warning("livesync Hub sink detach failed reason=%s: %s", reason, exc)
    finally:
        connection._mrson_hub_bridge = None
        _clear_livesync_armed(connection)


async def maybe_idle_detach_livesync(
    connection: "ImageDisplayClientConnection",
) -> None:
    """Drop idle LiveSync subscribers; detach the sink when none remain (safety net)."""
    if not getattr(connection, "_livesync_armed", False):
        return
    bridge = getattr(connection, "_mrson_hub_bridge", None)
    if bridge is not None and len(bridge.subscribers):
        if not bridge.subscribers.has_idle(LIVESYNC_IDLE_DETACH_SECONDS):
            return
        try:
            removed = await connection.run_on_main_thread(
                lambda: bridge.prune_idle_on_main(LIVESYNC_IDLE_DETACH_SECONDS)
            )
        except Exception as exc:
            LOGGER.warning("livesync idle prune failed: %s", exc)
            removed = []
        if removed:
            LOGGER.info("livesync idle subscribers dropped: %s", removed)
        if len(bridge.subscribers):
            return
        await detach_livesync_hub_sink(connection, reason="idle-all-subscribers")
        return
    last = float(getattr(connection, "_livesync_last_inbound", 0.0) or 0.0)
    if last <= 0.0:
        return
    idle = time.monotonic() - last
    if idle < LIVESYNC_IDLE_DETACH_SECONDS:
        return
    await detach_livesync_hub_sink(
        connection, reason=f"idle-{int(idle)}s"
    )


def _wire_from_scene_update_context(context: Any) -> Optional[Any]:
    if isinstance(context, list):
        for item in context:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "").strip().lower()
            if key != LIVESYNC_CONTEXT_KEY:
                continue
            return item.get("resource")
        return None
    if isinstance(context, dict):
        if LIVESYNC_CONTEXT_KEY in context:
            return context.get(LIVESYNC_CONTEXT_KEY)
        if "livesync" in context:
            return context.get("livesync")
    return None


def _livesync_scene_update_message(
    *, topic: str, wire: Dict[str, Any], target_subscriber: str = ""
) -> Dict[str, Any]:
    msg: Dict[str, Any] = {
        "event": {
            "hub.topic": topic,
            "hub.event": "scene-update",
            "context": [
                {
                    "key": LIVESYNC_CONTEXT_KEY,
                    "resource": wire,
                }
            ],
        }
    }
    if target_subscriber:
        msg["target.subscriber.name"] = target_subscriber
    return msg


def _message_requester(message: Dict[str, Any]) -> str:
    return str(message.get("subscriber.name") or message.get("subscriber") or "").strip()


async def handle_scene_update(
    connection: "ImageDisplayClientConnection",
    client: Any,
    message: Dict[str, Any],
) -> None:
    """Handle inbound Hub scene-update (LiveSync wire)."""
    event = message.get("event") if isinstance(message.get("event"), dict) else {}
    context = event.get("context")
    wire = _wire_from_scene_update_context(context)
    if not isinstance(wire, dict):
        LOGGER.debug("scene-update ignored: no livesync wire resource")
        return

    op = str(wire.get("op") or "").strip()
    requester = _message_requester(message)
    if op:
        _mark_livesync_inbound(connection)
        bridge = getattr(connection, "_mrson_hub_bridge", None)
        if bridge is not None and requester:
            bridge.subscribers.touch(requester)

    if op == "subscribe":
        await _respond_to_subscribe(connection, client, wire, requester)
        return

    if op == "unsubscribe":
        await _unsubscribe(connection, requester)
        return

    if op == "ping":
        # Keepalive from an open LiveSync subscriber; activity already marked above.
        return

    if op in ("applyOps", "reconcile", "getNode"):
        await _forward_op_to_mrson_peer(connection, wire)
        return

    LOGGER.debug("scene-update livesync op ignored: %s", op or "(event)")


async def _forward_op_to_mrson_peer(
    connection: "ImageDisplayClientConnection",
    wire: Dict[str, Any],
) -> None:
    from image_display_mrson_hub_sink import get_or_create_bridge

    bridge = get_or_create_bridge(connection)

    def run() -> None:
        bridge.deliver_op_on_main(wire)

    try:
        await connection.run_on_main_thread(run)
    except Exception as exc:
        LOGGER.warning(
            "livesync forward op=%s failed: %s", wire.get("op"), exc
        )


def _hash_set_from_export(
    scene_doc: Dict[str, Any], blob_parts: List[Tuple[str, bytes]]
) -> Set[str]:
    from image_display_mrson_hub_sink import collect_sha256_hashes

    hashes: Set[str] = set(collect_sha256_hashes(scene_doc))
    for name, _ in blob_parts:
        n = str(name or "").strip()
        if n.lower().endswith(".bin"):
            n = n[:-4]
        if n.startswith("sha256-"):
            hashes.add(n)
    return hashes


async def _publish_hub_blobs_and_snapshot(
    connection: "ImageDisplayClientConnection",
    client: Any,
    topic: str,
) -> Tuple[Set[str], Optional[Dict[str, Any]]]:
    """Export scene, publish HubBlobs multipart, then Snapshot JSON.

    Returns ``(published_hashes, scene_doc)``.
    """
    from live_scene_export import (
        build_livescene_hub_blobs_scene_update_message,
        export_live_scene_document,
    )

    def export_on_main() -> tuple:
        scene_doc, blob_parts = export_live_scene_document()
        msg = build_livescene_hub_blobs_scene_update_message(
            topic=str(topic),
            blob_parts=blob_parts,
        )
        return scene_doc, blob_parts, msg

    try:
        scene_doc, blob_parts, msg = await asyncio.wait_for(
            connection.run_on_main_thread(export_on_main),
            timeout=LIVESYNC_EXPORT_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        LOGGER.warning("livesync subscribe: LiveScene export failed: %s", exc)
        return set(), None

    hash_set = _hash_set_from_export(scene_doc, blob_parts)

    if blob_parts:
        try:
            status = await client.publish(msg)
            LOGGER.info(
                "livesync subscribe: scene-update HubBlobs blobs=%d http=%s",
                len(blob_parts),
                status,
            )
        except Exception as exc:
            LOGGER.warning(
                "livesync subscribe: HubBlobs scene-update failed: %s", exc
            )
    else:
        try:
            await client.publish(
                _livesync_scene_update_message(
                    topic=topic,
                    wire={"event": HUB_BLOBS_EVENT, "files": []},
                )
            )
        except Exception as exc:
            LOGGER.warning("livesync empty HubBlobs publish failed: %s", exc)

    try:
        await client.publish(
            _livesync_scene_update_message(
                topic=topic,
                wire={"event": SNAPSHOT_EVENT, "scene": scene_doc},
            )
        )
        LOGGER.info(
            "livesync subscribe: scene-update Snapshot nodes=%d",
            len(scene_doc.get("nodes") or {}),
        )
    except Exception as exc:
        LOGGER.warning("livesync Snapshot publish failed: %s", exc)

    return hash_set, scene_doc


async def _publish_metadata_snapshot(
    connection: "ImageDisplayClientConnection",
    client: Any,
    topic: str,
    types: List[str],
    requester: str,
) -> None:
    """Metadata-only first paint for one follower (no export / HubBlobs)."""
    from image_display_mrson_hub_sink import get_or_create_bridge

    bridge = get_or_create_bridge(connection)
    try:
        scene_doc = await asyncio.wait_for(
            connection.run_on_main_thread(lambda: bridge.metadata_snapshot_on_main(types)),
            timeout=LIVESYNC_EXPORT_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        LOGGER.warning("livesync metadata Snapshot failed: %s", exc)
        return
    try:
        await client.publish(
            _livesync_scene_update_message(
                topic=topic,
                wire={"event": SNAPSHOT_EVENT, "scene": scene_doc},
                target_subscriber=requester,
            )
        )
        LOGGER.info(
            "livesync subscribe: metadata Snapshot nodes=%d to=%s",
            len(scene_doc.get("nodes") or {}),
            requester or "*",
        )
    except Exception as exc:
        LOGGER.warning("livesync metadata Snapshot publish failed: %s", exc)


async def _unsubscribe(
    connection: "ImageDisplayClientConnection", requester: str
) -> None:
    bridge = getattr(connection, "_mrson_hub_bridge", None)
    if bridge is None:
        _clear_livesync_armed(connection)
        return
    try:
        none_left = await connection.run_on_main_thread(
            lambda: bridge.unsubscribe_on_main(requester)
        )
    except Exception as exc:
        LOGGER.warning("livesync unsubscribe %s failed: %s", requester or "?", exc)
        none_left = True
    LOGGER.info(
        "livesync unsubscribe: %s (remaining=%s)",
        requester or "?",
        bridge.subscribers.names(),
    )
    if none_left:
        await detach_livesync_hub_sink(connection, reason="unsubscribe")


async def _respond_to_subscribe(
    connection: "ImageDisplayClientConnection",
    client: Any,
    wire: Dict[str, Any],
    requester: str = "",
) -> None:
    topic = connection.get_topic() or ""
    if not topic:
        LOGGER.warning("livesync subscribe: no topic")
        return

    types_raw = wire.get("types")
    types: List[str] = []
    if isinstance(types_raw, list):
        types = [str(t).strip() for t in types_raw if str(t).strip()]

    local_bulk_raw = wire.get("localBulk")
    local_bulk: List[str] = []
    if isinstance(local_bulk_raw, list):
        local_bulk = [str(t).strip() for t in local_bulk_raw if str(t).strip()]

    metadata_only = bool(wire.get("metadataOnly"))

    from image_display_mrson_hub_sink import get_or_create_bridge

    bridge = get_or_create_bridge(connection)
    if metadata_only:
        await _publish_metadata_snapshot(connection, client, topic, types, requester)
    else:
        published, _scene = await _publish_hub_blobs_and_snapshot(
            connection, client, topic
        )
        bridge.mark_hashes_published(set(published))

    def subscribe_peer() -> bool:
        return bridge.subscribe_on_main(requester, types, local_bulk, metadata_only)

    try:
        resubscribed = await connection.run_on_main_thread(subscribe_peer)
        _mark_livesync_inbound(connection)
        LOGGER.info(
            "livesync subscribe: %s types=%s localBulk=%s metadataOnly=%s peer=%s",
            requester or "?",
            types or "*",
            local_bulk,
            metadata_only,
            "resubscribed" if resubscribed else "unchanged",
        )
    except Exception as exc:
        # First paint uses Snapshot; live updates need ModuleServer Hub sink.
        LOGGER.warning("livesync subscribe: Hub sink peer failed: %s", exc)
