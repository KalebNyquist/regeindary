# Regeindary Roadmap

Architectural priorities for the next round of active development, in recommended order.
Written 2026-11-11 after reviewing the codebase as of commit `1427798` (2025-12-24) plus uncommitted WIP.
Revised 2026-11-11 after a landscape review (competitors, AI, geopolitics).

Check items off (`- [x]`) as they land.

## Strategic direction (decision pending)

<!-- TODO(Kaleb): word this section. Outline below is a placeholder. -->

- **Landscape shift:** _What changed since 2025 — breadth commoditized (GiveRadar, GlobalGiving Atlas), Candid
  repositioning toward AI data supply, civic-space pressure (foreign-agent laws, US tax-exempt actions, aid cuts)._
- **Proposed positioning:** _Historical depth over breadth — dated registry snapshots, change/deregistration
  tracking, entity–filing links, financial time series, self-hosted for research resilience._
- **Relationship to Nipwiss:** _What Nipwiss needs from Regeindary going forward._
- **Decision gate:** _Confirm or reject the positioning after the evaluation items in "Before resuming
  development"; don't start priority #5+ until decided._
- **Open questions:** _..._

## Before resuming development

One-time checks after the 2025-12 → 2026-11 break. Collapse or delete this section once complete.

### Preserve what exists (time-sensitive)

- [ ] **Preserve existing raw downloads** — copy current caches (including the 2024-12 IRS files) somewhere safe
      before any refresh. `check_for_cache()` redownloads overwrite the cache, and old source files may not be
      retrievable again.
- [ ] **Back up MongoDB** — `mongodump --db regeindary` and `mongodump --db regeindary_dev` before running
      the new matcher (it writes `entityId_mongo` across hundreds of thousands of filings). Also confirm what
      `regeindary_dev` actually contains.
- [ ] **Stop using the `[y] Delete all old records` import option** — it destroys history. Use `[i]`
      (incremental) until change tracking (#5) exists.

### Evaluate

- [ ] **Evaluate GiveRadar** — does it have filings? historical snapshots? What does its CC BY 4.0 licence
      actually cover, given upstream registry terms? Is any of it self-hostable? Determines whether it is a
      competitor, an input, or both.
- [ ] **Ask Nipwiss** — would historical / status-change data help, or does it only use current state?
- [ ] **Search for existing registry archives** — does anyone already keep dated snapshots of charity registries?
- [ ] **Verify data sources** — confirm each `api_url` in `scripts/*/metadata.json` still resolves. Expect
      schema drift (renamed/added columns) that will surface as silent `mapping.json` gaps.
- [ ] **Watch for dependency drift** — the fresh uv venv pulls latest versions (notably pandas, pymongo).
      Suspect version changes before code when something breaks; see priority #1 for pinning.
- [ ] **Check Nipwiss** — review what Nipwiss currently queries/expects before changing anything that touches the
      shared MongoDB contract.

### Housekeeping

- [ ] **Refresh CLAUDE.md** — remove the stale "Always push to `claude/claude-md-…`" branch instruction; update
      registry count (Ireland), codebase size (~3,700 lines), and document `FilingMatcher` as the matching path.
      Update the competitive landscape table (add GiveRadar; note Candid's AI repositioning) and revisit
      "Avoid duplicating CharityBase's UK work".
- [ ] **GitHub hygiene** — triage `gh issue list`, `gh pr list`, and stale remote `claude/*` branches
      (`git branch -r`).
- [ ] **Define the first milestone** — e.g. matcher WIP committed + `pyproject.toml` (#1) + utils dual-import fix
      (#2) + one small registry re-imported cleanly.

## In-flight work to finish first

- [ ] Test the `FilingMatcher` menu flow (interface option 4) against `regeindary_dev`, then commit the WIP
      (excluding `scripts/config.toml`).
  - Note: the number entered at "How many matches to make?" is used as `limit`; `batch_size` is hard-coded to 1000.
- [ ] Finish Ireland support and update CLAUDE.md / README.md to list 5 registries.

## Architectural priorities

- [ ] **1. Package with `pyproject.toml` (uv)**
  No dependency manifest exists; deps (pymongo, pandas, requests, beautifulsoup4, tqdm, zipfile-deflate64) are
  only described in CLAUDE.md. `uv init` + `uv add ...` makes the environment reproducible.

- [ ] **2. Fix the dual import of `utils`** *(latent bug)*
  `scripts/interface.py` does `import utils`; every `scripts/*/retrieve.py` does `from scripts.utils import *`.
  Python treats these as two separate modules, so a registry import creates two MongoClients and two independent
  `cache` dicts. Remove the `sys.path.append` workarounds in `interface.py` and `utils.py` and use one
  package-qualified import path everywhere.

- [ ] **3. Move raw data out of `scripts/` into dated snapshots**
  `scripts/UnitedStates/filings/` holds ~1.66M XML files (~800MB), plus `zips_x/` and large IRS CSVs, none of
  which are gitignored. Move to a top-level, gitignored, IDE-excluded `data/<Country>/<YYYY-MM-DD>/` layout (or an
  external path configured in `config.toml`). Snapshots are immutable — never overwritten — with a checksum
  manifest per snapshot. Add a `data_dir` helper in utils and update hard-coded paths in the retrieve scripts.

- [ ] **4. Stop connecting to MongoDB at import time**
  `utils.py` calls `get_mongo_dbs()` at module load, so nothing can be imported or tested without a live database
  and `config.toml`. Replace the module-level globals with a lazily created connection accessor.

- [ ] **5. Change tracking and provenance** *(new — core of proposed positioning)*
  Replace delete-and-reinsert with upsert-and-diff (`upsert_all_to_mongodb()` already exists in utils but isn't
  exposed in the menu). Add fields such as `firstSeen`, `lastSeen`, `removedDate`, a status history, and a
  `snapshotDate` tying each record to the snapshot it came from. All additive, so non-breaking under the Nipwiss
  contract; update `schemas/*.json` and CLAUDE.md accordingly.

- [ ] **6. One filing-matching path**
  Once `FilingMatcher` is validated, retire `utils.match_filing()` and `utils.run_all_match_filings()`.
  Move US-specific EIN handling out of `filing_matcher.py` into the UnitedStates registry module.

- [ ] **7. Contract tests for the Nipwiss schema**
  No tests exist. A small pytest suite validating mapped sample records against `schemas/*.json` (field names,
  ISO 8601 date strings, numeric types), including the history/provenance fields from #5. Depends on #4.

- [ ] **8. Config hygiene**
  `scripts/config.toml` is tracked and currently points at `regeindary_dev`. Commit a `config.example.toml`,
  gitignore the real file, and/or allow an environment-variable override of `database_name`.

- [ ] **9. Split `utils.py` (~1,450 lines) by concern**
  Suggested modules: config/db connection, ingest (send/preview/upsert), registry metadata, indexes,
  diagnostics (status check, random entity), and Nipwiss-facing helpers (`get_all_urls`, etc.).

- [ ] **10. Repo-root tidy**
  Consolidate or remove the AI-generated analysis docs (`CODEBASE_EXPLORATION_SUMMARY.txt`,
  `DETAILED_CODEBASE_ANALYSIS.md`, `DEVELOPER_PATTERNS.md`, `QUICK_REFERENCE.md`); move `scratch.py` and
  `scripts/debug_*.py` into `dev/`. Consider a `.gitattributes` (`* text=auto`) to normalize line endings.

- [ ] **11. Registry plugin discovery** *(demoted — breadth is no longer the goal)*
  `interface.py` hard-codes the country menu (`range(1, 6)` with a TODO). Discover registries from folders that
  contain `metadata.json` + `retrieve.py`, and keep the shared `run_everything` skeleton in one place.

- [ ] **12. Data ethics and privacy note** *(new)*
  Document how person-level data (trustees, officers) is handled and what Regeindary should never publish or
  link. Required before any Shadow Registry work, given foreign-agent laws and civic-space pressure.

## Deliberately out of scope

- **Web API, ORM, async I/O** — don't serve the "depth over breadth" goal and would make the Nipwiss data
  contract harder to keep stable.
- **Competing on country count** — breadth is commoditized; use external sources for coverage instead.
- **Shadow Registry** — remains a separate future project, gated on the ethics note (#12).
