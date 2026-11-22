# Slicer image display client

Hub image display client for 3D Slicer (`imagingstudy-open`, `status-request`,
annotations, conference, and — when **Share my DICOMDB** is enabled —
`slicerworklist-request`, `slicerstudyinfo-request`, `livescene-request`,
`dicom-request` → `dicom-send`, `scene-update`).

STATUS replies with `source` / `product` / open ImagingStudy `context` /
`sceneview` only (no local DICOM `studies` list). Worklist fills its Slicer table
via `slicerworklist-request` and row details via `slicerstudyinfo-request`
(see `docs/module/slicerworklist-readme.md`) only when Share my DICOMDB is on
(module checkbox, or `--share-dicomdb` for the standalone script).

Web viewers open Slicer-local DICOM studies by sending `dicom-request`; this client
exports files from `slicer.dicomDatabase` and publishes multipart `dicom-send`
when sharing is enabled.

## Run without Slicer WebSub module

Requires 3D Slicer with DICOM database open:

```bash
pip install -e python_client
Slicer --python-script image_display/run_image_display.py -- --local --topic USER-1
# share local DICOM DB / LiveSync:
Slicer --python-script image_display/run_image_display.py -- --local --topic USER-1 --share-dicomdb
```

## Library

Runtime code lives in `lib/` (`image_display_client_hub.py`, loaders, handlers).
