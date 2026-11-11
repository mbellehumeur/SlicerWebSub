# Standalone Hub components

Run these from a clone of [SlicerWebSub](https://github.com/mbellehumeur/SlicerWebSub) **without** opening the Slicer Hub module in 3D Slicer.

All runtime folders live under **`WebSubInterface/`**.

## Prerequisites

```bash
cd WebSubInterface
pip install -e python_client
```

Python 3.9+ recommended.

---

## hub/

Hub / FHIRcast hub (FastAPI + WebSockets).

```bash
cd WebSubInterface/hub
pip install -r requirements.txt
python hub.py --port 2018
```

- Admin: http://127.0.0.1:2018/api/hub/admin  
- Cloud deploy: [WebSubInterface/hub/azure-webapp.md](../hub/azure-webapp.md)

---

## SlicerWebSub-workers/

Standalone service providers (no Slicer UI).

```bash
cd WebSubInterface
pip install -r ../SlicerWebSub-workers/requirements.txt
python ../SlicerWebSub-workers/neuro_seg/neuro_seg.py --local
python ../SlicerWebSub-workers/total_segmentator/total_segmentator.py --local
```

`--local` uses `http://127.0.0.1:2018`. Default is cloud `SLICER-HUB-CLOUD`. Preset `client_secret` values are public mock placeholders (see `SlicerWebSub-workers/hub_presets.py`); do not put real IdP secrets there.

Examples: `neuro_seg/neuro_seg.py`, `lung_screening/lung_screening.py`, `total_segmentator/total_segmentator.py` (`TOTALSEG`). TotalSeg also needs TotalSegmentator installed in the Python that runs inference—prefer a dedicated env, not Slicer’s module `pip_install`; see [total_segmentator/README.md](../../../SlicerWebSub-workers/total_segmentator/README.md). `torchxrayvision/torchxrayvision.py` (`TORCHXRAYVISION`) is currently a TotalSeg clone; see [torchxrayvision/README.md](../../../SlicerWebSub-workers/torchxrayvision/README.md).

Product docs: each folder under `SlicerWebSub-workers/<product>/README.md`.

---

## image_display/

Slicer as an image display client (`3DSLICER-ID` actor). Requires **3D Slicer** and an open DICOM database, but **not** the Slicer Hub module.

```bash
cd WebSubInterface
Slicer --python-script image_display/run_image_display.py -- --local --topic USER-1
```

Flags: `--local`, `--topic`, `--hub`, `--product-name`.

---

## python_client/

Shared Python wire-protocol client (`HubClient`, `SlicerHubClient`).

```bash
cd WebSubInterface
pip install -e python_client
```

```python
from hub_client import SlicerHubClient, HubConfig, SessionConfig
```

---

## Browser image display

VolView and OHIF ship in the hub deploy zip. For local dev, use vtk-js / VolView builds against the same hub port.
