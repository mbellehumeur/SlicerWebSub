# WebSubInterface Testing

Shared live and offline smoke scripts for the Hub extension:

- `hub/` — local hub HTTP / mock OAuth
- `python_client/` — `hub_client` subscribe / publish / request
- `image_display/` — offline ImagingStudy context helpers (no Slicer)

Offline scripts under `hub/`, `python_client/`, and `image_display/` that need no live hub
are registered as CTest targets (`WebSubInterface_<script>`) when the extension is built
with `BUILD_TESTING=ON`. Live smokes still need a hub on `:2018` and are run by hand.

## Prerequisites

```bash
cd WebSubInterface
pip install -e python_client
# aiohttp comes with hub-client
```

## Start local hub

```bash
cd WebSubInterface/hub
python hub.py --port 2018
```

## Run all live smokes (+ offline ID context)

```bash
cd WebSubInterface
python Testing/Python/run_live_smokes.py
```

Individual scripts:

```bash
python Testing/Python/hub/smoke_hub_http.py
python Testing/Python/hub/test_admin_access.py
python Testing/Python/hub/test_admin_ws_ticket.py
python Testing/Python/hub/test_conference_membership.py
python Testing/Python/hub/test_publish_conference_filters.py
python Testing/Python/python_client/smoke_client_pubsub.py
python Testing/Python/image_display/test_imaging_study_context.py
python Testing/Python/image_display/test_safe_zip_extract.py
python Testing/Python/image_display/test_livesync_subscribers.py
python Testing/Python/python_client/test_event_names.py
python Testing/Python/python_client/test_oidc_loopback_state.py
python Testing/Python/hub/test_oauth_client_state.py
python Testing/Python/hub/test_oidc_public_base_url.py
python Testing/Python/hub/test_service_mode_responses.py
python Testing/Python/hub/test_binary_publish_body_cap.py
```

Defaults: topic `USER-1`, endpoints from `SLICER-HUB` (`http://127.0.0.1:2018`).
