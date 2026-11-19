# Slicer image display client

Hub image display client for 3D Slicer (`imagingstudy-open`, `status-request`,
`slicerworklist-request`, `slicerstudyinfo-request`, `livescene-request`,
`dicom-request` → `dicom-send`, etc.).

STATUS replies with `source` / `product` / open ImagingStudy `context` /
`sceneview` only (no local DICOM `studies` list). Worklist fills its Slicer table
via `slicerworklist-request` and row details via `slicerstudyinfo-request`
(see `docs/module/slicerworklist-readme.md`).

Web viewers open Slicer-local DICOM studies by sending `dicom-request`; this client
exports files from `slicer.dicomDatabase` and publishes multipart `dicom-send`.

## Run without Slicer WebSub module

Requires 3D Slicer with DICOM database open:

```bash
pip install -e python_client
Slicer --python-script image_display/run_image_display.py -- --local --topic USER-1
```

## Library

Runtime code lives in `lib/` (`image_display_client_hub.py`, loaders, handlers).
