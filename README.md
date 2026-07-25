# Scraping Take-Home - NYCRR Title 15

![Prompt evidence screenshot](images/Captura%20de%20pantalla%202026-07-24%20132042.png)

# PROFESSOR COPY/PASTE GUIDE (WINDOWS + POWERSHELL)

## 0) Install and environment preparation

Copy and paste this block first:

```powershell
# 0.1) Go to project root
Set-Location "c:\Users\User\Downloads\regulation-scraper Dev Test\regulation-scraper Dev Test"

# 0.2) Create virtual environment (first time only)
py -3.13 -m venv .venv

# 0.3) Activate virtual environment
(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& ".\.venv\Scripts\Activate.ps1")

# 0.4) Install dependencies
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
```

## 1) Run the scraper with a refreshed Westlaw cookie

Open the **Visual Studio Code integrated terminal**, select **PowerShell**, and copy and paste this exact block:

```powershell
# 1) Go to the project root
Set-Location "C:\Users\User\Downloads\regulation-scraper Dev Test\regulation-scraper Dev Test"

# 2) Allow scripts for this terminal session and activate the virtual environment
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& ".\.venv\Scripts\Activate.ps1"

# 3) Configure the scraper
$env:PYTHONPATH='src'
$env:WESTLAW_CACHE_ONLY='0'
$env:WESTLAW_REQUEST_DELAY='0.35'

# 4) Use the validated JSONL route manifest
$manifest='output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1'
$env:WESTLAW_UNITS_JSONL="$manifest/reg_unit/new_york_todo.jsonl"
$env:WESTLAW_SECTIONS_JSONL="$manifest/reg_section/new_york_todo.jsonl"

# 5) Enter the Westlaw cookie without storing it in PowerShell history
$secureCookie=Read-Host "Paste the complete Westlaw cookie value" -AsSecureString
$env:WESTLAW_COOKIE=[System.Net.NetworkCredential]::new("", $secureCookie).Password

# 6) Set the browser request headers
$env:WESTLAW_USER_AGENT='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36'
$env:WESTLAW_ACCEPT_LANGUAGE='en-US,en;q=0.9'
$env:WESTLAW_REFERER='https://govt.westlaw.com/nycrr/Index'

# 7) Run the scraper
.\.venv\Scripts\python.exe -m regulation_scraper --state new_york_todo output
```

When PowerShell displays `Paste the complete Westlaw cookie value`, paste only the value of the browser's `Cookie` request header, without the `Cookie:` label, and press Enter. The pasted value remains hidden while it is entered.

Keep the same terminal open while the scraper runs because the environment variables are scoped to that PowerShell session.

## 2) Verify the generated output

Run this block after scraping completes:

```powershell
$latest=Get-ChildItem output -Directory |
   Sort-Object LastWriteTime -Descending |
   Select-Object -First 1

$u=Join-Path $latest.FullName 'reg_unit/new_york_todo.jsonl'
$s=Join-Path $latest.FullName 'reg_section/new_york_todo.jsonl'
$summaryExcel=Join-Path $latest.FullName 'new_york_todo_scrape.xlsx'
$fullExcel=Join-Path $latest.FullName 'new_york_todo_from_json_full_content.xlsx'
$contentExcel=Join-Path $latest.FullName 'new_york_todo_sections_content.xlsx'

"output=$($latest.FullName)"
"units=$((Get-Content $u | Measure-Object -Line).Lines)"
"sections=$((Get-Content $s | Measure-Object -Line).Lines)"
"placeholders=$((Select-String -Path $s -Pattern 'Please click here to continue').Count)"
"summary_excel=$(Test-Path $summaryExcel)"
"full_content_excel=$(Test-Path $fullExcel)"
"sections_content_excel=$(Test-Path $contentExcel)"
```

The validated result is 95 units, 646 sections, zero placeholders, and three Excel checks equal to `True`.

## Executed test and generated files

A full scraping test was executed and produced valid output with 95 units and 646 sections.

- Final output folder: [output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1](output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1)
- Units file (JSONL): [new_york_todo.jsonl](output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/reg_unit/new_york_todo.jsonl)
- Sections file (JSONL): [new_york_todo.jsonl](output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/reg_section/new_york_todo.jsonl)
- Summary report (Excel): [new_york_todo_scrape.xlsx](output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/new_york_todo_scrape.xlsx)
- Full-content report (Excel): [new_york_todo_from_json_full_content.xlsx](output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/new_york_todo_from_json_full_content.xlsx)
- Section-content report (Excel): [new_york_todo_sections_content.xlsx](output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/new_york_todo_sections_content.xlsx)

## Quick start for reviewer

All commands in this guide are intended to run in the **Visual Studio Code integrated terminal** using **PowerShell**.

Before starting, verify your shell and project folder:

```powershell
$PSVersionTable.PSVersion
Get-Location
```

### 1) Set up environment

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
```

### 2) Run the validated scraping flow

If hierarchical online navigation breaks due to intermittent Westlaw challenge/bridge behavior,
use a JSONL route manifest as a preventive method to avoid secondary issues
(partial runs, repeated timeouts, and empty pages in deep branches).

This flow still fetches each Document and generates fresh output, but avoids depending on
online Browse-tree expansion when that step is unstable.

Use the complete PowerShell block in [Run the scraper with a refreshed Westlaw cookie](#1-run-the-scraper-with-a-refreshed-westlaw-cookie). It includes the validated manifest, secure cookie prompt, request headers, and scraper command.

Technical confirmation: yes, this delivery used this preventive JSONL-route method
to mitigate broken online navigation and improve run stability.

### 3) If Westlaw blocks requests (403/Cloudflare), refresh headers/cookie and rerun

1. Open Westlaw in a browser and complete any challenge/captcha if shown.
2. Copy the complete value of the `Cookie` request header from a successful NYCRR request.
3. Run the complete PowerShell block above again and paste the refreshed value into its secure cookie prompt.

If you close the terminal or open a new tab, run the complete block again because PowerShell environment variables are session-scoped.

### 4) Verify generated files

- Units JSONL: [output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/reg_unit/new_york_todo.jsonl](output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/reg_unit/new_york_todo.jsonl)
- Sections JSONL: [output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/reg_section/new_york_todo.jsonl](output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/reg_section/new_york_todo.jsonl)
- Exported Excel: [output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/new_york_todo_scrape.xlsx](output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/new_york_todo_scrape.xlsx)

## Assignment objective

Implement a scraper for **Title 15 (Motor Vehicles)** from NYCRR, following the same structure as the California scraper, and produce:

- RegulationUnit (hierarchy pages that contain content-section pages)
- RegulationSection (leaf content pages)

## Requirements and implemented solution

1. Requirement: NYCRR Title 15 scraper with structure equivalent to California.
   Solution: Implemented in [src/regulation_scraper/scrapers/new_york_todo.py](src/regulation_scraper/scrapers/new_york_todo.py), preserving the `RegulationUnit` and `RegulationSection` schema model.
   Rationale: Keep compatibility with the existing pipeline and expected output format.

2. Requirement: Extract units and sections with hierarchy and status (active/repealed).
   Solution: The scraper detects link type (`Browse` vs `Document`), builds hierarchy, and marks `REPEALED` when the title contains `(Repealed)` or `[Repealed]`.
   Rationale: Meet take-home business logic and preserve regulatory data semantics.

3. Requirement: Tolerate blocking/transient errors (Cloudflare/403/timeouts) in real scraping.
   Solution: Added retries, backoff, timeout rotation, and HTTP session reset for transient failures.
   Rationale: Increase robustness in real online runs.

4. Requirement: Avoid secondary issues when hierarchical online navigation is unstable.
   Solution: Added preventive manifest mode (`WESTLAW_UNITS_JSONL` and `WESTLAW_SECTIONS_JSONL`) that prioritizes known-good routes.
   Rationale: Reduce incomplete runs and keep output consistency under dynamic anti-bot behavior.

5. Requirement: Keep changes focused on New York scraper work.
   Solution: Main implementation lives in [src/regulation_scraper/scrapers/new_york_todo.py](src/regulation_scraper/scrapers/new_york_todo.py), aligned with existing architecture.
   Rationale: Respect assignment scope and minimize lateral impact.

## How to run (online mode)

1. Create environment and install dependencies:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
```

2. Run NY scraper (online):

```powershell
$env:PYTHONPATH='src'
$env:WESTLAW_CACHE_ONLY='0'
$env:WESTLAW_REQUEST_DELAY='0.6'
# Optional: refreshed headers/cookie if Cloudflare requires it
.\.venv\Scripts\python.exe -m regulation_scraper --state new_york_todo output
```

## Persistence to avoid full re-scraping

- Local persistent HTTP cache: [.cache](.cache)
- Final scraping output (source of truth for delivery):
   - [output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/reg_unit/new_york_todo.jsonl](output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/reg_unit/new_york_todo.jsonl)
   - [output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/reg_section/new_york_todo.jsonl](output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/reg_section/new_york_todo.jsonl)
- Requested Excel export:
   - [output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/new_york_todo_scrape.xlsx](output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/new_york_todo_scrape.xlsx)
   - [output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/new_york_todo_from_json_full_content.xlsx](output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/new_york_todo_from_json_full_content.xlsx)
   - [output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/new_york_todo_sections_content.xlsx](output/2026-07-24_19_21_30-4e7f52c5-b1cc-42fc-afa2-d2e0e43fe7c1/new_york_todo_sections_content.xlsx)

With these versioned files, full scraping does not need to be repeated for review or downstream usage.

## Operational note

If Westlaw invalidates cookies/session, a new online run may become partial. In that case, refresh headers/cookies and rerun. Meanwhile, the versioned JSONL/XLSX artifacts allow work to continue without data loss.
