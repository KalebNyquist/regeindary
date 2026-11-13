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
- [x] **Back up MongoDB** — done 2026-11-12: `mongodump --gzip` of all databases to
      `~/mongo-backups/2026-11-12/` (3.1 GB; `regeindary` 8.7 GB on disk → 2.6 GB, 10,444,790 filings).
      Restore: `mongorestore --gzip --nsInclude "<db>.*" <dir>`. The server also holds `regeindary_alt` and the
      `NIPWISS3-*` databases (see Evaluate). Still to confirm what `regeindary_dev` contains (Step 1c).
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
      shared MongoDB contract. Note: Nipwiss *stores* its own data (`NIPWISS3-cnc` ~2 GB, `-cnc2`, `-test`) on the
      same `mongod` server, so server-level changes (upgrades, data-dir moves) affect both projects.
- [ ] **Evaluate `regeindary_alt`** (358 MB, 3 collections) — recalled as a development branch with an improved
      data structure, meant to eventually replace `regeindary`. Diff its schema against `regeindary` and the
      Nipwiss contract; decide whether to adopt, mine for ideas, or drop. Relevant to #5 (change tracking).

### Housekeeping

- [ ] **Refresh CLAUDE.md** — currently 1,044 lines vs. the documented <200-line target
      ([memory docs](https://code.claude.com/docs/en/memory.md)). Rule of thumb: *always true* → CLAUDE.md;
      *when touching X* → path-scoped rule / subdirectory CLAUDE.md; *when doing Y* → skill; *must happen* → hook/settings.
  - [ ] Run `/context all` and `/doctor prompt-audit` to see what loads and what's flagged
  - [ ] Delete stale/dangerous content: `claude/…` branch instruction, "Last Updated" stats,
        line/registry counts, function inventories that duplicate the code
  - [ ] Decide: keep the Nipwiss contract as condensed always-loaded rules (~30 lines) +
        full detail in a path-scoped rule (`.claude/rules/nipwiss-contract.md`, paths: `schemas/**`, `scripts/utils.py`)
  - [ ] Move strategy + Shadow Registry vision to `docs/STRATEGY.md`; refresh competitor
        table there (add GiveRadar; note Candid's AI repositioning; revisit "Avoid duplicating CharityBase's UK work")
  - [ ] Move registry quirks into per-country `scripts/<Country>/CLAUDE.md` (load on demand)
  - [ ] Convert workflows ("add a registry", incremental update) into skills under `.claude/skills/`
  - [ ] Decide what must be *enforced* rather than requested (e.g. never commit `config.toml`)
        → hook / settings / .gitignore, not prose
  - [ ] Decide: CLAUDE.md vs AGENTS.md (AGENTS.md if you'll use other AI coding tools)
  - [ ] Decide: what goes in CLAUDE.local.md (personal, e.g. "dev DB is regeindary_dev")
  - [ ] Document `FilingMatcher` as the matching path; update registry count (Ireland); point to
        ROADMAP.md for current priorities
  - [ ] Verify: new session, `/context all`, then ask Claude a Nipwiss-contract question to confirm the rules still load
- [ ] **GitHub hygiene** — triage `gh issue list`, `gh pr list`, and stale remote `claude/*` branches
      (`git branch -r`).
- [ ] **Define the first milestone** — e.g. matcher WIP committed + `pyproject.toml` (#1) + utils dual-import fix
      (#2) + one small registry re-imported cleanly.

## In-flight work to finish first

Started 2026-11-11 as a "warm-up" before the time-sensitive items above.

- [x] **Step 0: Rebuild the dev environment with uv** (commit `2db2147`, 2026-11-11)
  - Old `.venv` was on CPython 3.16.0a1 (alpha, uv auto-picked newest) with no packages; deleted and rebuilt.
  - Pinned Python 3.14 (`.python-version`), `uv init --bare`, `uv add pymongo pandas requests beautifulsoup4 tqdm`.
  - Resolved: Python 3.14.10, pandas 3.1.1, numpy 2.5.4, pymongo 4.19.0, python-dateutil 4.0.0.
  - ⚠️ **pandas 3.x and python-dateutil 4.x are major-version jumps** from what the code was written against —
    first suspects if anything breaks (fallback: `uv add "pandas<3"`).
  - Run `!` commands from Claude Code in Git Bash — use forward slashes (`.venv/Scripts/python`).
- [x] **Step 1: Test the `FilingMatcher` menu flow** (interface option 4) against `regeindary_dev`
  - [x] 1a. Confirm MongoDB tools (2026-11-12): installed Database Tools 100.20.1 via
        `winget install MongoDB.DatabaseTools`; added `C:\Program Files\MongoDB\Tools\100\bin` to user PATH
        (installer doesn't); restart PyCharm to pick it up. Server ping `{ ok: 1 }`.
  - [x] 1b. Back up (2026-11-12) — all databases, see "Back up MongoDB" above
  - [x] 1c. Status check (2026-11-12): Australia 63,776 orgs (no `download_completion`), E&W 389,646 orgs /
        1,205,927 filings, Ireland 14,339 / 80,485, NZ 44,085; no US. 80,973 filings had `entityId_mongo: null`
        (= unmatched; `$exists` counts them as matched). One org has no known `registryID` (511,847 vs 511,846).
  - [x] 1d. Bulk, skip orphans, limit 100 (2026-11-12) — found and fixed 3 bugs in `_resolve_org_matches()`:
        int keys vs str lookups (all fresh lookups → false orphans; "create orphans" would duplicate orgs);
        E&W `subsidiary_filter` `$or` overwrote the ID `$or` via `dict.update` (fetched all ~390k orgs);
        Ireland org IDs stored as `double` → `str()` gave `"20000011.0"` (added `_id_key()` normalizer).
        Results: 0/1000 → 488/1000 → 1000/1000 matched; 1000/1000 links spot-checked correct.
        Open: `limit` < `batch_size` still processes a full batch (1000).
  - [x] 1e. Repeat with aggregation method on a small limit — expect 0 matched: aggregation filters
        `{"$exists": False}` and ignores `null`, unlike bulk (`None`). Unify the "unmatched" filter first.
        Also: its `$toString` in `$lookup` defeats the index; it doesn't write org `filings` arrays.
        Done 2026-11-13 (`e4e1a1b`): shared `UNMATCHED_FILTER = {"entityId_mongo": None}`. Limit 100 → exactly
        100 Ireland matched; 1,100/1,100 Ireland + 1,000/1,000 E&W sampled links correct. Ireland's double IDs
        match without `_id_key()` because Mongo's `$toString(20000011.0)` gives `"20000011"`.
  - [x] 1f. Commit the WIP (excluding `scripts/config.toml`)
  - Followups found during 1e
    - [ ] Piped stdout crashes on emoji (cp1252); workaround `PYTHONUTF8=1`. Fix: `sys.stdout.reconfigure(encoding="utf-8")`
    - [ ] interface.py option 4: `try` wraps `match_all()`, so `except ValueError` swallows real errors and catches `UnicodeEncodeError` etc.
    - [ ] Menu prompts print a literal `\n` (`"\\n..."` in `interface.py`)
    - [ ] "Orphans skipped" in aggregation stats actually means "still unmatched"
    - [ ] "Falling back to bulk for: United States…" message printed even with no US filings
  - Note: the number entered at "How many matches to make?" is used as `limit`; `batch_size` is hard-coded to 1000.
- [ ] **Step 2: Finish Ireland support** — findings from 2026-11-11 inspection of the cached CSVs (Effective Date
      9 Nov 2025):
  - [ ] Back up `scripts/Ireland/cache_*.csv` before any re-download (they are a historical snapshot)
  - [ ] Fix `mapping.json` drift: `Registration Date`, `Website`, `Date Filed`, `Charity Number` don't exist in
        the CSVs; filing headers contain embedded newlines (`"Period\nStart Date"`), so `Period Start/End Date`
        never match. Only `Gross Income` / `Gross Expenditure` / entity number & name match today.
  - [ ] Fix encoding order in `retrieve.py`: `latin-1` never fails, so `cp1252` is unreachable and `€` becomes
        `\x80`. Try `utf-8` → `cp1252` → `latin-1`.
  - [ ] Fix pandas-download path: it saves without the title row, but the reader uses `header=1` → real header
        is skipped.
  - [ ] **IDs violate the Nipwiss contract (strings):** Ireland org `entityId` is `double` (likely pandas NaN →
        float64 from blank rows), E&W is `int`. Normalize at import (reuse `filing_matcher._id_key`), audit others.
  - [ ] **Dates and numbers violate the Nipwiss contract:** periods are `DD/MM/YYYY` (mapping wrongly says
        MM/DD), money is text like `€24,393,381,000`.
  - [ ] Decide: Ireland-only cleaning vs. a generic transform in `utils.py`. **Cross-registry finding:** the
        `"format"` key in every `mapping.json` (Australia, Ireland, NewZealand, UnitedStates) is never read by
        any code — dates are stored raw everywhere. Likely needs a generic fix + audit of other registries.
  - [ ] Re-import to `regeindary_dev`; verify with options 3 (keyword match) and 5 (random entity)
  - [ ] Update CLAUDE.md / README.md to list 5 registries

## Architectural priorities

- [x] **1. Package with `pyproject.toml` (uv)** — done 2026-11-11 (`2db2147`), see Step 0 above.
  - [ ] Remaining: US module still imports `zipfile-deflate64` (no wheels since cp310; needs C build tools on
        Windows). Replace with the maintained `inflate64` package when returning to US work.
  - [ ] Optional: loosen `requires-python` from `>=3.14` to `>=3.11` if other machines (e.g. Nipwiss) need it.

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
