# Regeindary Roadmap

Architectural priorities for the next round of active development, in recommended order.
Written 2026-11-11 after reviewing the codebase as of commit `1427798` (2025-12-24) plus uncommitted WIP.

Check items off (`- [x]`) as they land.

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

- [ ] **3. Move raw data out of `scripts/`**
  `scripts/UnitedStates/filings/` holds ~1.66M XML files (~800MB), plus `zips_x/` and large IRS CSVs, none of
  which are gitignored. This slows IDE indexing, search tools, and backups, and risks an accidental mass commit.
  Move to a top-level `data/<Country>/` (gitignored and IDE-excluded) or an external path configured in
  `config.toml`; add a `data_dir` helper in utils and update hard-coded paths in the retrieve scripts.

- [ ] **4. Stop connecting to MongoDB at import time**
  `utils.py` calls `get_mongo_dbs()` at module load, so nothing can be imported or tested without a live database
  and `config.toml`. Replace the module-level globals with a lazily created connection accessor.

- [ ] **5. One filing-matching path**
  Once `FilingMatcher` is validated, retire `utils.match_filing()` and `utils.run_all_match_filings()`.
  Move US-specific EIN handling out of `filing_matcher.py` into the UnitedStates registry module.

- [ ] **6. Split `utils.py` (~1,450 lines) by concern**
  Suggested modules: config/db connection, ingest (send/preview/upsert), registry metadata, indexes,
  diagnostics (status check, random entity), and Nipwiss-facing helpers (`get_all_urls`, etc.).

- [ ] **7. Registry plugin discovery**
  `interface.py` hard-codes the country menu (`range(1, 6)` with a TODO). Discover registries from folders that
  contain `metadata.json` + `retrieve.py`, and keep the shared `run_everything` skeleton in one place.

- [ ] **8. Contract tests for the Nipwiss schema**
  No tests exist. A small pytest suite validating mapped sample records against `schemas/*.json` (field names,
  ISO 8601 date strings, numeric types) would catch the breaking changes CLAUDE.md warns about. Depends on #4.

- [ ] **9. Config hygiene**
  `scripts/config.toml` is tracked and currently points at `regeindary_dev`. Commit a `config.example.toml`,
  gitignore the real file, and/or allow an environment-variable override of `database_name`.

- [ ] **10. Repo-root tidy**
  Consolidate or remove the AI-generated analysis docs (`CODEBASE_EXPLORATION_SUMMARY.txt`,
  `DETAILED_CODEBASE_ANALYSIS.md`, `DEVELOPER_PATTERNS.md`, `QUICK_REFERENCE.md`); move `scratch.py` and
  `scripts/debug_*.py` into `dev/`.

## Deliberately out of scope

Web API, ORM, async I/O. These don't serve the "depth over breadth" goal and would make the Nipwiss data
contract harder to keep stable.
