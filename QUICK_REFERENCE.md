# Regeindary Quick Reference Guide

## File Manifest

| File | Lines | Purpose | Key Functions |
|------|-------|---------|---|
| interface.py | 102 | CLI menu system | menu_select(), retrieve_registries() |
| utils.py | 426 | Database ops + utilities | send_to_mongodb(), match_filing(), run_all_match_filings() |
| config.toml | 5 | Configuration | MongoDB connection details |
| Australia/retrieve.py | 92 | AU data retrieval | retrieve_data(), run_everything() |
| Australia/mapping.json | 19 | AU field mapping | 4 field mappings |
| EnglandWales/retrieve.py | 117 | E&W data retrieval | retrieve_data(), retrieval_with_unzip(), run_everything() |
| EnglandWales/mapping.json | 42 | E&W field mapping | 10 field mappings |
| NewZealand/retrieve.py | 85 | NZ data retrieval | retrieve_data(), run_everything() |
| NewZealand/mapping.json | 23 | NZ field mapping | 5 field mappings |
| UnitedStates/retrieve.py | 503 | US data retrieval | retrieve_entities(), retrieve_locations_of_filing_zips(), run_everything() |
| UnitedStates/mapping.json | 47 | US field mapping | 11 field mappings |
| entity.json | 91 | Entity schema | 13 standardized fields |
| filing.json | 68 | Filing schema | 8 standardized fields |

**Total Python Code**: ~1,300 lines across 6 files

## Quick Start for Developers

### 1. Understanding Data Flow
```
User selects country in interface.py
  ↓
Country's retrieve.py runs
  ↓
retrieve_data(): Downloads and caches source data
  ↓
run_everything(): Orchestrates upload
  ├─ retrieve_mapping() - loads mapping.json
  ├─ meta_check() - gets/creates registry metadata
  ├─ send_all_to_mongodb() - applies mapping & inserts
  └─ completion_timestamp() - records completion
  ↓
MongoDB stores standardized records
```

### 2. Key Concepts

**Entities**: Organizations/charities from registry
- Primary identifier: entityId (or entityIndex for UK)
- Must include: entityName
- May include: website, established date, etc.

**Filings**: Annual reports/tax returns
- Primary identifier: filingId (or recordId)
- Links to entities via: entityId_mongo (post-matching)
- Must include: financial period dates
- May include: income, expenses, etc.

**Mapping**: Field translation rules
```json
{"origin": "Source_Field", "target": "entityName"}
```

### 3. Modifying Existing Code

**To fix a field mapping issue**:
1. Run "Keyword Match Assist" (menu option 3)
2. Edit the country's mapping.json
3. Re-run retrieval (select Y to delete old records)

**To handle encoding issues**:
```python
pd.read_csv(url, encoding_errors="backslashreplace")
```

**To add progress tracking**:
```python
if (i % 100 == 0) or (i == len(records)):
    percentage = "%.2f" % (100 * i/len(records))
    print(f"\r {i}/{len(records)} ({percentage}%)", end="")
```

### 4. Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| "Too many" exception in meta_check() | Duplicate registry entries | Manually clean MongoDB registries collection |
| UnicodeDecodeError in menu | Previous operation interrupted | Restart interface.py |
| Match filing fails with 2+ matches | Data quality issue | Investigate duplicate entityIds in source |
| Filings don't match to entities | entityId format mismatch | Check US ID padding: `.rjust(9, '0')` |
| Orphan filings created | Missing source organization | Expected behavior - breadcrumb metadata added |

### 5. Testing a New Registry Before Full Import

```python
# 1. Import retrieve module directly
from scripts.NewCountry import retrieve as new_country

# 2. Get sample records
raw_dicts = new_country.retrieve_data("NewCountry/")
print(raw_dicts[0])  # Inspect first record

# 3. Test mapping
from scripts.utils import retrieve_mapping
mapping = retrieve_mapping("NewCountry/")
print(mapping)

# 4. Test small batch
send_all_to_mongodb(raw_dicts[:10], mapping, {"registryID": test_id})

# 5. Verify in MongoDB
db.organizations.find_one({"registryID": test_id})
```

### 6. Database Indexes

Created by `index_check()`:
- organizations: (registryID, entityId), (registryID, entityIndex)
- filings: (registryID, entityId)

These enable fast matching of filings to entities.

### 7. Legal Notices

Each registry includes legalNotices array:
- Australia: Creative Commons Attribution 3.0 Australia
- EnglandWales: None (but data is from UK government)
- NewZealand: Unsolicited Electronic Messages Act 2007
- UnitedStates: Database Contents License (DbCL) v1.0

Store in database: `{"legalNotices": [...]}`

### 8. Configuration Keys

From config.toml:
```
mongo_path         → MongoDB connection URI
database_name      → "regeindary"
organization_collection → "organizations"
filings_collection → "filings"
meta_collection    → "registries"
```

To change: Edit config.toml, restart Python

### 9. Field Name Patterns

Learn from existing mappings:

**Australia**:
- entityName ← Charity_Legal_Name
- entityId ← ABN
- establishedDate ← Date_Organisation_Established

**EnglandWales**:
- entityName ← charity_name
- entityId ← registered_charity_number
- entityIndex ← organisation_number

**NewZealand**:
- entityName ← Name
- entityId ← CharityRegistrationNumber
- entityIndex ← OrganisationId

**UnitedStates**:
- entityId ← EIN
- entityName ← NAME (or OrganizationName for filings)
- filingId ← ObjectId

### 10. Debugging Steps

1. **Check Status**
   - Menu option 1: See all counts and timestamps

2. **Review Mappings**
   - Menu option 3: See what fields are mapped vs. unmapped

3. **Inspect Raw Data**
   - Menu option 5: Display random entity with Original Data

4. **Query MongoDB Directly**
   ```python
   from scripts.utils import mongo_regeindary
   docs = mongo_regeindary.organizations.find(
       {"registryID": ObjectId("...")}, limit=5
   )
   ```

5. **Check Cache Files**
   ```bash
   ls -la Australia/cache*.csv
   ls -la EnglandWales/cache*.json
   ```

## Architecture Diagram

```
┌────────────────────────────────────────────────────────────┐
│ User Interface (interface.py - menu_select())             │
│ [1] Status  [2] Retrieve  [3] Match Assist  [4] Match [5] │
└─────────────────┬──────────────────────────────────────────┘
                  │
    ┌─────────────┼─────────────┬──────────────┬──────────────┐
    │             │             │              │              │
    ▼             ▼             ▼              ▼              ▼
 Australia   EnglandWales  NewZealand    UnitedStates      Utils
retrieve.py retrieve.py    retrieve.py    retrieve.py       ├─ Config
    │             │             │              │         ├─ Cache
    │             │             │              │         ├─ MongoDB
    └─────────────┴─────────────┴──────────────┘              │
                  │                                           │
                  ▼                                           │
        ┌─────────────────────────────────────────────────────┤
        │  Mapping (mapping.json)  ←────────────────────────┘
        │  field origin → field target
        └─────────────────┬────────────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────────────────────────┐
        │  MongoDB (regeindary database)                      │
        ├─────────────────────────────────────────────────────┤
        │  registries:     metadata about sources             │
        │  organizations:  entity records (standardized)      │
        │  filings:        filing records (standardized)      │
        └─────────────────────────────────────────────────────┘
```

## Environment Requirements

```
Python:        3.11+ (uses tomllib)
MongoDB:       8.0.0+ (tested), running on localhost:27017
pymongo:       Recent version
pandas:        Recent version
requests:      For HTTP operations
beautifulsoup4: For web scraping (US only)
tqdm:          For progress bars (US only)
zipfile-deflate64: ZIP extraction (US only)
boto3:         Optional, for AWS S3 (US filings alternative)
```

## Code Location Quick Map

**Want to...** | **Look in...**
---|---
Add a menu option | `interface.py` (lines 55-96)
Change MongoDB connection | `config.toml` and `utils.py` get_mongo_dbs()
Add a field mapping | Country's `mapping.json`
Modify data retrieval | Country's `retrieve.py`
Change field standardization | `schemas/entity.json` or `schemas/filing.json`
Add entity-filing link logic | `utils.py` match_filing()
See all registries | `utils.py` list_registries()

