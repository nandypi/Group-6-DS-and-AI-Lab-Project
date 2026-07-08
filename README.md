# Group 6 DS and AI Lab Project

## Overview

Retail and SME investors in Indian capital markets often receive the same public disclosures as institutional investors, but they usually lack the tools and research teams needed to interpret them quickly.

This project aims to process corporate announcements, exchange filings, PDF reports, and regulatory updates so that useful information can be filtered, summarized, and presented through a simplified dashboard.

The current data preparation work focuses on filtering stock exchange announcement metadata and preparing PDF file lists for downstream processing.

## Data Preparation Pipeline

```text
data/announcements_metadata-last-year.json
        |
        v
datapreparation/pdf_seperate.py
        |
        +--> data/processed/keep.json
        +--> data/processed/reject.json
        +--> data/processed/review.json

data/processed/keep.json
data/processed/review.json
        |
        v
datapreparation/create_keep_file_list.py
        |
        +--> data/processed/keep-file-list.json
        +--> data/processed/review-file-list.json
```

## Python Files

| File | Purpose | Input | Output |
| --- | --- | --- | --- |
| `datapreparation/pdf_seperate.py` | Classifies announcement metadata into `keep`, `reject`, and `review` groups. | `data/announcements_metadata-last-year.json` | `data/processed/keep.json`, `data/processed/reject.json`, `data/processed/review.json` |
| `datapreparation/create_keep_file_list.py` | Creates smaller file-list JSONs containing only the fields needed for PDF processing. | `data/processed/keep.json`, `data/processed/review.json` | `data/processed/keep-file-list.json`, `data/processed/review-file-list.json` |

## JSON Files

| File | Meaning |
| --- | --- |
| `data/announcements_metadata-last-year.json` | Source metadata file containing full announcement records. This must exist before running `datapreparation/pdf_seperate.py`. |
| `data/processed/keep.json` | Full records selected for further processing. These announcements are considered useful based on category or text keywords. |
| `data/processed/reject.json` | Full records rejected from further processing. These announcements are considered routine or less useful for the current goal. |
| `data/processed/review.json` | Full records that could not be confidently classified. These require manual review. |
| `data/processed/keep-file-list.json` | Reduced version of `keep.json` containing only `desc`, `attchmntText`, and `attchmntFile`. |
| `data/processed/review-file-list.json` | Reduced version of `review.json` containing only `desc`, `attchmntText`, and `attchmntFile`. |

## `pdf_seperate.py` Classification Logic

`datapreparation/pdf_seperate.py` reads the full announcement metadata and separates each record into one of three groups.

### 1. Keep

Records are added to `keep` when their `desc` value belongs to important disclosure categories such as:

- acquisitions
- board meeting outcomes
- press releases
- dividend updates
- financial result updates
- director changes
- buyback-related announcements

These records are expected to be useful for later analysis and summarization.

### 2. Reject

Records are added to `reject` when their `desc` value belongs to routine or less relevant categories such as:

- trading window updates
- record dates
- newspaper publications
- loss of share certificates
- ESOP-related updates
- takeover regulation disclosures

These records are filtered out from further processing.

### 3. Keyword-Based Filtering

Some broad categories need extra filtering using `attchmntText`.

The script applies keyword checks when `desc` is one of:

- `Updates`
- `General Updates`
- `Shareholders meeting`
- `Analysts/Institutional Investor Meet/Con. Call Updates`

Useful keywords move the record to `keep`, including:

```text
transcript
investor presentation
acquisition
partnership
collaboration
ceo
director
brsr
form 20-f
press release
```

Less useful keywords move the record to `reject`, including:

```text
schedule of meet
investor conference
notice of agm
voting results
scrutinizer report
proceedings
```

If neither useful nor less useful keywords are found, the record is added to `review`.

## Reduced File-List Format

`datapreparation/create_keep_file_list.py` creates compact JSON files for records that need PDF-level processing.

Each item in `keep-file-list.json` and `review-file-list.json` has this structure:

```json
{
  "desc": "Updates",
  "attchmntText": "Announcement text shown by the exchange.",
  "attchmntFile": "https://example.com/file.pdf"
}
```

Only these three fields are kept because they identify:

| Field | Meaning |
| --- | --- |
| `desc` | Announcement category. |
| `attchmntText` | Short text description of the announcement. |
| `attchmntFile` | URL of the attached PDF file. |

## Run Order

Run the scripts in this order:

```bash
python datapreparation/pdf_seperate.py
python datapreparation/create_keep_file_list.py
```
