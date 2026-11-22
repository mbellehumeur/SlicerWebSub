# Slicer worklist / studyinfo requests

Typed hub requests for the 3D Slicer Image Display local DICOM database.
Built via `request_event_for('SLICERWORKLIST')` / `requestEventFor('SLICERWORKLIST')`
(and the same for `SLICERSTUDYINFO`).

## Events

| Direction | Event | `context.dataType` |
|-----------|-------|-------------------|
| Request | `slicerworklist-request` | `SLICERWORKLIST` |
| Response | `slicerworklist-response` | `SLICERWORKLIST` |
| Request | `slicerstudyinfo-request` | `SLICERSTUDYINFO` |
| Response | `slicerstudyinfo-response` | `SLICERSTUDYINFO` |

Slicer ID must list both `*-request` events in `hub.events` when
**Share my DICOMDB** is enabled (see `DISPLAY_EVENTS` /
`display_events_for_share` in `image_display_client_hub.py`). With Share off,
those events are omitted from the subscribe list.

## Flow

1. Slicer ID connects with Share my DICOMDB checked and sends `status-request`
   (`target.actor: *`).
2. Worklist detects product `3DSLICER-ID`, enters **slicer mode** (dedicated table),
   answers STATUS with its open ImagingStudy context.
3. Worklist sends `slicerworklist-request` (`target.actor: ID`) → study-level rows.
4. Row click → `slicerstudyinfo-request` with `studyInstanceUID` → full ImagingStudy.
5. Open → `imagingstudy-open` (`open-mode: local-dicom`) as before.

## `slicerworklist-response` `data`

```json
{
  "source": "slicerworklist",
  "product": "3DSLICER-ID",
  "studies": [
    {
      "id": "slicer-dicom:<StudyInstanceUID>",
      "name": "Patient — description",
      "description": "...",
      "organization": "3d-slicer",
      "studyInstanceUID": "...",
      "patientName": "...",
      "patientID": "...",
      "studyDate": "YYYYMMDD",
      "modalities": ["CT"],
      "format": "DICOM",
      "openMode": "local-dicom"
    }
  ]
}
```

## `slicerstudyinfo-request` / `-response`

Request `event.context`:

```json
{
  "dataType": "SLICERSTUDYINFO",
  "studyInstanceUID": "1.2.3…"
}
```

Response `data` (FHIRcast-style ImagingStudy with series / instances from
`slicer.dicomDatabase`):

```json
{
  "source": "slicerstudyinfo",
  "product": "3DSLICER-ID",
  "ok": true,
  "context.type": "ImagingStudy",
  "context": [
    {
      "key": "study",
      "resource": {
        "resourceType": "ImagingStudy",
        "uid": "1.2.3…",
        "series": []
      }
    }
  ],
  "studyInstanceUID": "1.2.3…"
}
```

JS helpers: `requestHubSlicerWorklist` / `requestHubSlicerStudyInfo` in
`@slicer-hub/client`.
