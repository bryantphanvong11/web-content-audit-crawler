# Web Content Audit Crawler

A Python-based website content auditing and crawling pipeline for inventorying web pages and identifying technical, content, accessibility, link, form, and analytics issues.

> **Project status:** Initial public repository. The audit modules are being organized into a reusable pipeline as additional crawler and reporting components are added.

## What this project does

The project is designed to turn a website inventory into actionable audit data. Current components cover:

- HTTP-based page auditing and crawl inventory analysis
- HTTP status and redirect analysis
- Encoded URL / 404 investigation
- Duplicate-title and possible duplicate-content detection
- External form-link discovery
- PDF form candidate detection
- Form review dataset generation
- Links / duplicates dataset generation
- Automated accessibility testing with Playwright and Axe
- Google Analytics 4 path matching against crawl inventory
- CSV-based intermediate datasets and reports

## Architecture

The current workflow is centered around a technical inventory:

```text
Website
   │
   ▼
Crawl / Technical Inventory
   │
   ├── Status & Redirect Audits
   ├── Duplicate Detection
   ├── Link Analysis
   ├── Form Discovery
   ├── Accessibility Scan
   └── GA4 Matching
           │
           ▼
      CSV Reports
```

The repository is being structured so the individual audits can be run independently and later composed into a single end-to-end workflow.

## Project structure

```text
web-content-audit-crawler/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── scripts/
│   └── # audit scripts will be organized here
├── data/
│   ├── input/
│   └── output/
└── tests/
```

## Technology

- Python
- Requests
- Beautiful Soup
- RapidFuzz
- Playwright
- Axe accessibility testing
- Google Analytics 4 Data API
- Google Sheets API
- CSV-based data processing

## Installation

Clone the repository:

```bash
git clone https://github.com/bryantphanvong11/web-content-audit-crawler.git
cd web-content-audit-crawler
```

Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

For browser-based accessibility scans, install the Playwright browser:

```bash
playwright install chromium
```

## Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Do **not** commit real credentials, service-account keys, API tokens, or private website data.

## Data flow

Most audit scripts operate on CSV inventory data rather than requiring every audit to independently rediscover the entire website. This makes the pipeline easier to checkpoint, rerun, inspect, and combine with other datasets.

Typical inputs include:

- Page URL
- HTTP status code
- Content type
- Redirect information
- Page title
- Crawl metadata

Typical outputs include:

- Audit findings
- Duplicate groups
- Candidate forms
- External links
- Accessibility violations
- GA4-to-inventory matches
- Unmatched analytics paths

## Engineering features

The project uses several techniques that are useful when processing large websites:

- `requests.Session()` for repeated HTTP requests
- Request timeouts and controlled delays
- URL normalization and canonicalization
- Checkpoint/progress files for long-running scans
- CSV-based intermediate datasets
- Deduplication of discovered relationships
- Fuzzy title matching with RapidFuzz
- Browser automation for JavaScript-rendered accessibility testing
- Environment variables for external service configuration
- Separate audit stages so individual checks can be rerun without repeating the entire pipeline

## Roadmap

- [x] Publish project repository
- [ ] Organize existing audit scripts
- [ ] Add the primary crawler/discovery module
- [ ] Add reusable crawler utilities
- [ ] Add sample inventory data
- [ ] Add tests
- [ ] Add a single command-line entry point
- [ ] Add structured logging
- [ ] Add CI checks with GitHub Actions
- [ ] Add example audit output
- [ ] Document the full end-to-end pipeline

## Disclaimer

This repository is intended for authorized website auditing and development use. Only crawl or test websites when you have permission to do so, and respect applicable terms, robots directives, rate limits, and access controls.
