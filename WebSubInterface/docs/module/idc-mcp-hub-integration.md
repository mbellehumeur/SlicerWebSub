# IDC MCP server — Hub integration

This document summarizes what the hosted IDC MCP server provides today, and how
Hub clients open radiology series **without** a Hub-side `idc-index`.

**Hosted endpoint (reference):** `https://api.imaging.datacommons.cancer.gov/mcp`  
**Server info (as of probe):** IDC (Imaging Data Commons) v3 beta

---

## Tools available in the current MCP implementation

| Tool | Purpose |
|------|---------|
| `get_idc_version` | IDC data release and pinned index version |
| `get_stats` | Headline totals (collections, patients, studies, series, size TB) |
| `list_collections` | All IDC collections with cancer types, subjects, etc. |
| `get_collection` | Detailed metadata for one `collection_id` |
| `list_analysis_results` | Derived datasets (segmentations, radiomics, etc.) |
| `list_attributes` | Filterable cohort attributes (call before `build_cohort`) |
| `get_attribute_values` | Distinct values + counts for a categorical attribute |
| `list_tables` | SQL tables (`index`, modality indices, collections, etc.) |
| `get_table_schema` | Column names/types for a table |
| `list_clinical_tables` | Clinical tables available for cohort join |
| `get_clinical_table_schema` | Schema for a clinical table |
| `get_clinical_table` | Rows from a clinical table (filtered) |
| `build_cohort` | Structured filters → counts, sample series, download hints |
| `run_sql` | Read-only DuckDB SQL against the IDC index |
| `get_cohort_urls` | Public `s3://…/*` or `gs://…/*` **prefix per series** (CLI/s5cmd) |
| `get_viewer_url` | OHIF v3 or SLIM browser viewer URL for a series/study |
| `get_citations` | Publications to cite for a cohort |
| `get_licenses` | License breakdown (CC-BY vs CC-BY-NC, etc.) |
| `download_cohort` | Download DICOM to a **local directory** (local MCP only; uses idc-index/s5cmd) |

---

## How Hub opens radiology IDC (no Hub `idc-index`)

Hub uses IDC in three layers:

1. **Metadata search** — worklist NL (`POST /api/hub/idc-nl/search`) and/or public IDC REST / MCP.
2. **StudyUID → CRDC** — browser **slim CORS index** (`idc-rad-groups.json` + `idc-rad-slim.parquet` on Jetstream), via `@slicer-hub/client` `resolveIdcSeriesFromSlimIndex` (same path as SlicerLive IRA). Rebuild with SlicerLive `render/demos/build-idc-slim.ts`.
3. **Bytes** — client **ListObjectsV2** under `https://{bucket}.s3.amazonaws.com/{crdc}/` then GET `.dcm` (OHIF `load-hub-study-files`, IRA `idc_tools`).

`POST /api/hub/idc/series-files` and Hub `idc_index_service.py` were **removed**. Worklist Add with StudyInstanceUID uses the slim index → CRDC-prefix sample (same shape as View).

---

## Optional MCP addition: `get_series_file_urls`

MCP still returns series **prefixes** (`get_cohort_urls`), not per-instance HTTPS lists. Radiology Hub open no longer needs that on the Hub server (browser lists S3). A hosted MCP `get_series_file_urls` tool remains useful for CLI/download tooling and non-browser clients — same contract as `IDCClient.get_series_file_URLs()` in [idc-index](https://github.com/ImagingDataCommons/idc-index).

### Input

```json
{
  "series_instance_uid": "1.2.840.…",
  "source": "aws",
  "max_instances": 300
}
```

### Output

```json
{
  "series_instance_uid": "1.2.840.…",
  "source": "aws",
  "instance_count": 133,
  "files": [
    {
      "url": "https://idc-open-data.s3.amazonaws.com/{crdc-uuid}/{filename}.dcm",
      "fileName": "{filename}.dcm"
    }
  ]
}
```

---

## Hub client references

- Slim index: `@slicer-hub/client` `resolveIdcSeriesFromSlimIndex` / `enrichImagingStudyOpenPlanWithSlimIndex`.
- Worklist Add: `packages/worklist/idc-series-actions.ts` `resolveViaHubOrS3`.
- OHIF open: `packages/ohif-extension/src/hub/imaging-study-handler.ts`.
- NL search (kept on Hub): `POST /api/hub/idc-nl/search`.
