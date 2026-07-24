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

## 1) Run scraping (preventive JSONL manifest mode)

Copy and paste this exact block:

```powershell
# 1) Go to the project root
Set-Location "c:\Users\User\Downloads\regulation-scraper Dev Test\regulation-scraper Dev Test"

# 2) (Optional) activate venv
(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& ".\.venv\Scripts\Activate.ps1")

# 3) Preventive mode variables (JSONL manifest)
$env:PYTHONPATH='src'
$env:WESTLAW_CACHE_ONLY='0'
$env:WESTLAW_REQUEST_DELAY='0.35'
$env:WESTLAW_UNITS_JSONL='output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8/reg_unit/new_york_todo.jsonl'
$env:WESTLAW_SECTIONS_JSONL='output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8/reg_section/new_york_todo.jsonl'

# 4) Run scraping
.\.venv\Scripts\python.exe -m regulation_scraper --state new_york_todo output

# 5) Verify result (units, sections, and excel)
$latest=Get-ChildItem output -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$u=Join-Path $latest.FullName 'reg_unit/new_york_todo.jsonl'
$s=Join-Path $latest.FullName 'reg_section/new_york_todo.jsonl'
$x=Join-Path $latest.FullName 'new_york_todo_scrape.xlsx'
"latest_output=$($latest.Name)"
"units=" + (Get-Content $u | Measure-Object -Line).Lines
"sections=" + (Get-Content $s | Measure-Object -Line).Lines
"excel_exists=" + (Test-Path $x)
"excel_path=$x"
```

## Executed test and generated files

A full scraping test was executed and produced valid output with 95 units and 646 sections.

- Final output folder: [output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8](output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8)
- Units file (JSONL): [new_york_todo.jsonl](output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8/reg_unit/new_york_todo.jsonl)
- Sections file (JSONL): [new_york_todo.jsonl](output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8/reg_section/new_york_todo.jsonl)
- Final report (Excel): [new_york_todo_scrape.xlsx](output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8/new_york_todo_scrape.xlsx)

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

### 2) Run online scraping (normal flow)

```powershell
$env:PYTHONPATH='src'
$env:WESTLAW_CACHE_ONLY='0'
$env:WESTLAW_REQUEST_DELAY='0.6'
.\.venv\Scripts\python.exe -m regulation_scraper --state new_york_todo output
```

Note: run each line in the same VS Code terminal session so `$env:` variables remain active.

### 2.1) Preventive method (JSONL route manifest)

If hierarchical online navigation breaks due to intermittent Westlaw challenge/bridge behavior,
use a JSONL route manifest as a preventive method to avoid secondary issues
(partial runs, repeated timeouts, and empty pages in deep branches).

This flow still fetches each Document and generates fresh output, but avoids depending on
online Browse-tree expansion when that step is unstable.

```powershell
$env:PYTHONPATH='src'
$env:WESTLAW_CACHE_ONLY='0'
$env:WESTLAW_REQUEST_DELAY='0.35'

$env:WESTLAW_UNITS_JSONL='output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8/reg_unit/new_york_todo.jsonl'
$env:WESTLAW_SECTIONS_JSONL='output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8/reg_section/new_york_todo.jsonl'

.\.venv\Scripts\python.exe -m regulation_scraper --state new_york_todo output
```

Technical confirmation: yes, this delivery used this preventive JSONL-route method
to mitigate broken online navigation and improve run stability.

### 3) If Westlaw blocks requests (403/Cloudflare), refresh headers/cookie and rerun

1. Open Westlaw in a browser and complete any challenge/captcha if shown.
2. Copy request headers from a valid page (for example, SiteList or NYCRR).
3. Update env vars and rerun:

```powershell
$env:WESTLAW_COOKIE='PASTE_FULL_COOKIE_HERE'

$env:PYTHONPATH='src'
$env:WESTLAW_CACHE_ONLY='0'
$env:WESTLAW_REQUEST_DELAY='0.6'
$env:WESTLAW_USER_AGENT='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36'
$env:WESTLAW_ACCEPT_LANGUAGE='es-ES,es;q=0.9'
$env:WESTLAW_REFERER='https://govt.westlaw.com/SiteList'

$env:WESTLAW_SEED_URL='https://govt.westlaw.com/nycrr/Browse/Home/NewYork/UnofficialNewYorkCodesRulesandRegulations?guid=I03a0d260b02611dd831ccd7cddcc2f88&originationContext=documenttoc&transitionType=Default&contextData=(sc.Default)'
.\.venv\Scripts\python.exe -m regulation_scraper --state new_york_todo output
```

Note: if you close the terminal or open a new tab, set the `$env:` variables again before running.

### 4) Verify generated files

- Units JSONL: [output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8/reg_unit/new_york_todo.jsonl](output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8/reg_unit/new_york_todo.jsonl)
- Sections JSONL: [output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8/reg_section/new_york_todo.jsonl](output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8/reg_section/new_york_todo.jsonl)
- Exported Excel: [output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8/new_york_todo_scrape.xlsx](output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8/new_york_todo_scrape.xlsx)

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
  - [output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8/reg_unit/new_york_todo.jsonl](output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8/reg_unit/new_york_todo.jsonl)
  - [output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8/reg_section/new_york_todo.jsonl](output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8/reg_section/new_york_todo.jsonl)
- Requested Excel export:
  - [output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8/new_york_todo_scrape.xlsx](output/2026-07-24_17_29_34-b3b64b82-fbf7-4fe3-88c7-5e564ee423c8/new_york_todo_scrape.xlsx)

With these versioned files, full scraping does not need to be repeated for review or downstream usage.

## Operational note

If Westlaw invalidates cookies/session, a new online run may become partial. In that case, refresh headers/cookies and rerun. Meanwhile, the versioned JSONL/XLSX artifacts allow work to continue without data loss.
