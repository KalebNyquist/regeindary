# Regeindary Codebase Comprehensive Analysis

## 1. PROJECT OVERVIEW

**Project Name**: Regeindary  
**Purpose**: Import publicly-available data from heterogeneous civil society/organizational registries and standardize them in a MongoDB database  
**Key Concept**: Links "entities" (organizations) to "filings" (tax returns/annual reports)  
**Name Etymology**: Portmanteau of "reg**istr**y" + "stan**dar**d" (also evokes "legendary", "repository", "EIN")

## 2. DIRECTORY STRUCTURE

```
/home/user/regeindary/
├── .git/                          # Git repository
├── README.md                       # Project documentation
├── schemas/                        # Data schema definitions
│   ├── entity.json                # Entity/Organization schema
│   └── filing.json                # Filing schema
└── scripts/                        # Main application code
    ├── interface.py               # CLI entry point (menu system)
    ├── utils.py                   # Shared utilities and database operations
    ├── config.toml                # Configuration (MongoDB connection, collection names)
    ├── Australia/                 # Country-specific data retrieval
    │   ├── retrieve.py            # Australia data import logic
    │   └── mapping.json           # Field mapping (original -> standardized)
    ├── EnglandWales/              # England & Wales registry
    │   ├── retrieve.py            # E&W data import logic
    │   └── mapping.json           # Field mapping
    ├── NewZealand/                # New Zealand registry
    │   ├── retrieve.py            # NZ data import logic
    │   └── mapping.json           # Field mapping
    └── UnitedStates/              # US registry (IRS data)
        ├── retrieve.py            # US data import logic
        └── mapping.json           # Field mapping
```

## 3. CORE MODULES AND THEIR PURPOSES

### 3.1 `/scripts/interface.py` - CLI Entry Point
**Purpose**: Interactive command-line menu for user operations

**Key Functions**:
- `menu_select()`: Main menu loop with 6 operations
  - [1] Run Status Check
  - [2] Retrieve Registries (with country selection)
  - [3] Keyword Match Assist (verify field mappings)
  - [4] Match Filings with Entities
  - [5] Display Random Entity
  - [H] Hello World (test)
  - [x] Quit

- `retrieve_registries()`: Handles country selection and delegates to country-specific retrieve.py

**Design Pattern**:
- Dynamic imports of country-specific modules
- Lazy loading: imports only what user selects
- Clean separation between CLI and business logic

### 3.2 `/scripts/utils.py` - Core Business Logic & Database Operations
**Responsibility**: All MongoDB operations, shared utilities, file handling

**Global State** (initialized at module load):
```python
mongo_regeindary       # MongoDB database connection
collections_map       # Mapping: collection names
meta, orgs, filings    # Collection references
```

**Key Functions by Category**:

**Configuration Management**:
- `get_config()`: Loads config.toml using tomllib (Python 3.11+)
- `get_mongo_dbs()`: Establishes MongoDB connection and gets collection references

**Cache Management**:
- `check_for_cache(folder, label, suffix)`: Checks for cached files, prompts user

**Database Operations**:
- `send_to_mongodb(record, mapping, static, collection)`: Inserts single record with field mapping
- `send_all_to_mongodb(records, mapping, static, collection)`: Batch inserts with progress tracking
- `meta_check(registry_name, source_url, collection)`: Creates/retrieves registry metadata, handles old record deletion
- `delete_old_records(registry_id, collection)`: Prompts user to delete previous versions

**Metadata & Status**:
- `list_registries()`: Returns all registries from metadata collection
- `status_check()`: Displays counts, completion times, and database size statistics
- `completion_timestamp(meta_id, completion_type)`: Records download completion timestamp

**Mapping & Validation**:
- `retrieve_mapping(folder)`: Loads and parses mapping.json into dict format
- `keyword_match_assist(select)`: Compares mapping coverage against schema fields

**Entity-Filing Relationships**:
- `match_filing(filing, matching_field, auto_create_from_orphan)`: Links filings to entities
- `create_organization_from_orphan_filing(filing)`: Creates entity from orphan filing with metadata
- `run_all_match_filings(batch_size)`: Batch matching with progress tracking and interruption handling

**Data Retrieval**:
- `get_random_entity(display, mongo_filter, hard_limit)`: Retrieves random entity for testing

**Index Management**:
- `index_check(collection, identifiers)`: Creates composite indexes for performance

### 3.3 `/scripts/config.toml` - Configuration File
**Format**: TOML (Tom's Obvious, Minimal Language)

**Contents**:
```toml
mongo_path = "mongodb://127.0.0.1:27017/"
database_name = "regeindary"
organization_collection = "organizations"
filings_collection = "filings"
meta_collection = "registries"
```

**Pattern**: Simple key-value configuration, assumes local MongoDB instance

### 3.4 Country-Specific `/scripts/[Country]/retrieve.py` Files

**Common Structure** (all 4 countries follow same pattern):
1. Import statements with relative imports from utils
2. Global variables (API URLs, source URLs, headers, registry name)
3. `retrieve_data(folder)`: Downloads/caches source data
4. `run_everything(folder)`: Orchestrates retrieval → upload workflow
5. Optional main execution block

**Data Retrieval Methods**:

**Australia**:
- **Source**: CSV from data.gov.au (ACNC Charity Register)
- **Method**: Direct CSV download using pandas
- **Special Handling**: Custom encoding error handling ("backslashreplace")
- **Legal**: Creative Commons Attribution 3.0 Australia

**EnglandWales**:
- **Source**: Two JSON files from Azure Blob Storage (zipped)
  - Entities: publicextract.charity.json
  - Filings: publicextract.charity_annual_return_history.json
- **Method**: Download ZIP → Extract JSON → Parse
- **Special Handling**: UTF-8-sig encoding, dual dataset handling
- **Two Collections**: Entities AND filings in separate uploads

**NewZealand**:
- **Source**: CSV via OData API (charities.govt.nz)
- **Method**: HTTP GET → StringIO → pandas CSV parsing
- **Special Handling**: low_memory=False for large dataset
- **Legal**: Unsolicited Electronic Messages Act 2007 notice

**UnitedStates**:
- **Source**: Two sources
  - Entities: 4 regional CSV files from IRS (combined)
  - Filings: Metadata CSV from Giving Tuesday DataCommons
- **Method**: Multi-region download → concatenate DataFrames
- **Special Handling**: 
  - Region mapping (NE, Mid-Atlantic, Gulf, International)
  - Categorical columns preserved as strings
  - Progress bars with tqdm
  - S3 bucket interaction (optional)
  - Web scraping fallback for IRS website
- **Legal**: Database Contents License (DbCL) v1.0

### 3.5 `/scripts/[Country]/mapping.json` - Field Mapping Definition

**Structure**: Array of objects, each with:
```json
{
  "origin": "Original_Field_Name",
  "target": "standardizedFieldName",
  "format": "Optional_Format_String"
}
```

**Purpose**: Maps messy original field names → standardized schema fields

**Example** (Australia):
```json
{
  "origin": "Charity_Legal_Name",
  "target": "entityName"
},
{
  "origin": "ABN",
  "target": "entityId"
}
```

**Processing** (in utils.py):
```python
mapping = {feature['origin']: feature['target'] for feature in mp}
# Applied to each record: upload_dict[mapping[original_field]] = record_value
```

**Coverage Analysis**: Developers can run "Keyword Match Assist" to see:
- Fields already mapped (checkmark ✅)
- Fields NOT yet mapped (empty square ⬜)

## 4. DATABASE SCHEMAS

### 4.1 Entity Schema (`/schemas/entity.json`)

**JSON Schema 2020-12 Format**

**Key Fields** (standardized across all registries):

| Field | Type | Description | Uniqueness |
|-------|------|-------------|-----------|
| entityName | string | Listed name of organization | NO (can have duplicates) |
| entityId | string | Public registry ID | NOT unique (see subsidiaryId) |
| entityIndex | string | Internal registry index | UNIQUE |
| subsidiaryId | string | Nested org identifier | entityId + subsidiaryId = unique |
| associatedEntityIds | list | Related org IDs | - |
| websiteUrl | string (url) | Official organization URL | - |
| registryName | string | Source registry name | - |
| registeredDate | string (date) | Date entered registry | - |
| establishedDate | string (date) | Date org was founded | - |
| recordId | string | Record-specific ID | UNIQUE (for multiple years) |
| recordIndex | string | Internal record index | UNIQUE |
| sourceData | object | Metadata about data retrieval | - |

**Required Fields**: entityName, sourceData

**sourceData Structure**:
- dateAccessed (datetime): When data was fetched
- sourceUrl (url): Original source URL
- retrivalMethod (string): Tool used to extract
- rawData (object): Original data representation

### 4.2 Filing Schema (`/schemas/filing.json`)

**Similar structure to entity schema**

**Key Fields**:

| Field | Type | Description |
|-------|------|-------------|
| startDate | date | Period start |
| endDate | date | Period end |
| recordDate | date | Filing submission date |
| totalIncome | number | Total revenue |
| totalExpenditures | number | Total expenses |
| filingId | string | Public filing ID |
| filingIndex | string | Internal filing index |
| sourceData | object | Metadata (same as entity) |

**Required Fields**: None (optional schema)

**Note**: Comment in code suggests this may be merged with entity schema

### 4.3 MongoDB Collections

**Three Collections**:

1. **registries** (meta_collection):
   - Stores metadata about each data source
   - Fields:
     - _id: MongoDB ObjectId (returned as registryID)
     - name: Registry name (e.g., "Australia - ACNC Charity Register")
     - source: Source URL
     - download_completion: Datetime when retrieval finished
   - Purpose: Track what registries exist, when they were updated

2. **organizations** (organization_collection):
   - Stores entity records
   - Created by: Australia, EnglandWales, NewZealand, UnitedStates retrieve.py
   - Common fields added:
     - registryID: Foreign key to registries._id
     - registryName: Name of source registry
     - legalNotices: Array of license info
     - Original Data: Unmodified source record
   - Indexes: (registryID, entityId), (registryID, entityIndex)

3. **filings** (filings_collection):
   - Stores filing records
   - Created by: EnglandWales, UnitedStates retrieve.py
   - Contains: entityId_mongo field (relationship link after matching)
   - Indexes: (registryID, entityId)

### 4.4 Data Addition Process

**Flow**: Original Record → Mapping → MongoDB Document

```python
# Step 1: Create base document with static fields
upload_dict = {
    "registryID": meta_id,
    "registryName": registry_name,
    "legalNotices": [...]
}

# Step 2: Apply mapping (original -> standardized)
for original_field, standardized_field in mapping.items():
    if original_field in record:
        upload_dict[standardized_field] = record[original_field]

# Step 3: Preserve original
upload_dict["Original Data"] = record

# Step 4: Insert
result = collection.insert_one(upload_dict)
```

## 5. DATA FLOW: RETRIEVAL TO DATABASE STORAGE

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: USER INITIATES RETRIEVAL                           │
│ - interface.py menu → user selects country                 │
│ - Dynamic import of country/retrieve.py                    │
│ - Call run_everything(folder)                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ STEP 2: RETRIEVE DATA FROM SOURCE                          │
│ - retrieve_data(folder):                                   │
│   - Check cache (prompt if cached exists)                 │
│   - Download from API/web if not cached                   │
│   - Save to local cache file (CSV/JSON)                   │
│   - Parse into list of dicts                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ STEP 3: LOAD METADATA & MAPPING                            │
│ - retrieve_mapping(folder) → Load mapping.json             │
│ - meta_check(registry_name, source_url):                   │
│   - If new: create registry entry, return _id              │
│   - If exists: prompt to delete old records or skip        │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ STEP 4: PREPARE UPLOAD DICT                                │
│ - Create static_amendment dict:                            │
│   - registryID (from metadata)                             │
│   - registryName                                           │
│   - legalNotices (CC, DbCL, etc.)                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ STEP 5: SEND TO MONGODB                                    │
│ - send_all_to_mongodb(records, mapping, static):          │
│   - For each record:                                       │
│     - Start with static_amendment                          │
│     - Apply mapping (field translation)                    │
│     - Add "Original Data" (unmodified record)              │
│     - insert_one(upload_dict) into collection              │
│     - Progress tracking every 100 records                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ STEP 6: FINALIZE                                           │
│ - completion_timestamp(meta_id) → timestamp database       │
│ - Return results dict                                      │
└─────────────────────────────────────────────────────────────┘
```

### OPTIONAL: Entity-Filing Matching

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 7: MATCH FILINGS TO ENTITIES (separate operation)    │
│ - run_all_match_filings(batch_size=None):                 │
│   - Create indexes on (registryID, entityId)               │
│   - Find all unmatched filings (no entityId_mongo field)   │
│   - For each filing:                                       │
│     - match_filing(filing):                                │
│       - Query: {"registryID": filing.registryID,           │
│                 "entityId": filing.entityId}               │
│       - If 0 matches → auto_create_from_orphan_filing()   │
│       - If 1 match → use matched org._id                   │
│       - If 2+ matches → raise exception                    │
│       - Update filing: entityId_mongo = org._id            │
│   - Progress tracking every 5 min                          │
│   - Graceful Ctrl+C handling                               │
└─────────────────────────────────────────────────────────────┘
```

## 6. CONFIGURATION PATTERNS AND CONVENTIONS

### 6.1 Naming Conventions

**Python File Naming**:
- `retrieve.py`: Data retrieval/upload for specific registry
- `mapping.json`: Field mapping file
- `interface.py`: CLI entry point
- `utils.py`: Shared utilities
- `config.toml`: Configuration

**Variable Naming**:
- Global module variables: UPPER_SNAKE_CASE (api_retrieval_point, registry_name)
- Functions: snake_case (retrieve_data, send_to_mongodb)
- Schema fields: camelCase (entityName, registryID, entityId_mongo)

**Collection Naming**:
- organizations: Stores entity records
- filings: Stores filing records
- registries: Metadata/tracking collection

**Field Naming Conventions** (standardized across all registries):
- **Identity**: entityId, entityName, entityIndex, subsidiaryId
- **Dates**: registeredDate, establishedDate, startDate, endDate, recordDate
- **Relationships**: registryID, registryName, entityId_mongo
- **Metadata**: legalNotices, Original Data, sourceData
- **Financial**: totalIncome, totalExpenditures

### 6.2 Import Patterns

**Path Setup** (consistent across all modules):
```python
import sys, os
project_root = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_root)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)
```
*Purpose*: Makes same code work in Anaconda PowerShell and PyCharm

**Country-specific retrieves**:
```python
from scripts.utils import *  # Star import
import pandas as pd
from requests import get
```

**Interface.py**:
```python
import utils  # Direct module import (in same directory)
```

### 6.3 Error Handling Patterns

**User Input Validation**:
- Menu: loops until valid selection
- Cache: loops on invalid y/n input
- Batch size: try/except for integer conversion

**Data Validation**:
- Status code check: `if response.status_code != 200: raise Exception`
- Encoding errors: backslashreplace mode for problematic encodings
- Duplicate matches: `elif len(matched_orgs) >= 2: raise Exception`

**User Interruption**:
- `try: ... except KeyboardInterrupt`: Graceful Ctrl+C handling in match_filing loop
- `except UnicodeDecodeError`: Signals previous operation interrupted

### 6.4 Progress Tracking Patterns

**Manual Progress**:
- Every 100 records: `if (i % 100 == 0) or (i == len(records)): print(percentage)`
- Every 5 minutes: Check time delta, print matched count

**Terminal Formatting**:
- Progress on same line: `print(..., end="\r")`
- Padding for alignment: `"✔".ljust(10)`, `x.ljust(longest_key_length + 2)`

**Library Progress**:
- tqdm: `with tqdm(total=total_size, unit='B'): for chunk ...`

## 7. DEPENDENCIES AND REQUIREMENTS

### Core Dependencies

| Package | Version | Purpose | Used By |
|---------|---------|---------|---------|
| Python | 3.11+ | Language requirement | All (uses tomllib from 3.11+) |
| pymongo | - | MongoDB driver | utils.py |
| pandas | - | CSV/Data manipulation | All retrieve.py files |
| requests | - | HTTP requests | EnglandWales, NewZealand, UnitedStates |
| beautifulsoup4 | - | HTML parsing | UnitedStates (web scraping) |
| tqdm | - | Progress bars | UnitedStates |
| zipfile-deflate64 | - | ZIP extraction (note) | UnitedStates (custom import) |
| boto3 | optional | AWS S3 access | UnitedStates (optional filings) |

### External Services

- **MongoDB**: Local instance at `mongodb://127.0.0.1:27017/`
- **Data Sources**:
  - Australia: data.gov.au CSV endpoint
  - EnglandWales: Azure Blob Storage (zipped JSON)
  - NewZealand: OData API (charities.govt.nz)
  - UnitedStates: IRS website (CSV + web scraping)

## 8. TESTING AND DEPLOYMENT PATTERNS

### 8.1 Testing Features Built Into Code

**Status Check** (`interface.py` option [1]):
- Counts registries, organizations, filings
- Shows completion timestamps
- Displays registry coverage percentages
- Reports total database size

**Keyword Match Assist** (`interface.py` option [3]):
- Picks random entity from selected registry
- Shows which schema fields are covered by mapping
- Shows which schema fields are NOT covered
- Useful for identifying incomplete mappings

**Random Entity Display** (`interface.py` option [5]):
- Retrieves random entity from database
- Option to hide "Original Data" field
- Hard limit to prevent excessive queries

**Caching Strategy**:
- First run: downloads from source, saves as cache
- Subsequent runs: prompts user to use cache or redownload
- Allows iterative testing without repeated network requests

### 8.2 Deployment Considerations

**No explicit deployment configuration found**, but implied pattern:
- Python script execution (local)
- Assumes MongoDB running on localhost:27017
- Can run from `/scripts` directory
- Interactive CLI (no automation/batch mode designed in)

**Scaling Notes** (from recent commits):
- Recent optimization of `run_all_match_filings()` for speed
- "Batch monitoring + termination speed" improvements
- "Improved... termination speed" suggests large dataset handling

## 9. CODE STYLE AND NAMING CONVENTIONS

### 9.1 Code Style Observations

**Formatting**:
- 4-space indentation
- Clear section separators (# Globals, # Functions)
- Comments above complex sections
- TODO comments marked with `# - [ ]` (checkbox format)

**Examples**:
```python
# - [ ] make sure this updates when adding a country (line 24, interface.py)
# - [ ] note UK/Wales works better when matching_field='entityIndex' (line 299, utils.py)
# - [ ] consider replacing with a pipeline (line 181, utils.py)
```

**String Formatting**:
- Mix of f-strings and .format()
- Status messages with checkmarks: `✔`, `✅`, `⬜`, `⚠️`
- ASCII art headers: "="s for section dividers

**Function Documentation**:
- Docstrings used selectively (not consistently)
- Inline comments for non-obvious logic
- Example: `meta_check()` has clear docstring explaining behavior

### 9.2 Module Structure Pattern

All country-specific `retrieve.py` files follow:
1. **Imports** (relative paths)
2. **Global Variables** (API URLs, headers, metadata)
3. **Helper Functions** (if needed)
4. **Main Functions** (retrieve_data, run_everything)
5. **Execution Block** (`if __name__ == '__main__'`)

### 9.3 Data Structure Patterns

**Dictionary for Configuration**:
```python
api_retrieval_points = {
    "entities": {"url": "...", "filename": "..."},
    "filings": {"url": "...", "filename": "..."}
}
```

**Collections Map**:
```python
collections = {
    "organizations": config['organization_collection'],
    "filings": config['filings_collection'],
    "registries": config['meta_collection']
}
```

**Mapping Structure** (JSON):
```json
[
  {"origin": "original_name", "target": "standardized_name", "format": "optional"},
  ...
]
```

## 10. IMPORTANT QUIRKS AND SPECIAL CONSIDERATIONS

### 10.1 Known Issues/TODOs in Code

1. **Australia Encoding**: Custom error handling for CSV encoding issues
2. **EnglandWales**: 
   - Better matching with `entityIndex` instead of `entityId`
   - Two separate datasets (entities + filings) 
   - Dual upload process

3. **NewZealand**: 
   - Requires `low_memory=False` for pandas
   - Legal notice about email anti-spam law (prominent warning)

4. **UnitedStates**: 
   - Most complex implementation
   - 4 regional files that must be concatenated
   - Custom zipfile_deflate64 import (unusual dependency)
   - Web scraping for Form 990 files (fragile)
   - Optional S3 bucket access for Giving Tuesday data
   - Windows-specific paths in some functions (backslashes)

### 10.2 Data Quality Issues

**Orphan Filings**: Filings without matching organizations
- Auto-creation enabled by default
- Created org cloned from filing with breadcrumb metadata
- Questionable: US filings have websites, orgs don't

**Entity ID Formatting**:
- US data: IDs padded to 9 digits with zeros (`.rjust(9, '0')`)
- Comment indicates "import error with USA Data" workaround
- Should be fixed in source if possible

**Duplicate Organization Matches**:
- Expected: 0 matches (auto-create) or 1 match
- If 2+ matches: Exception raised (data integrity issue)

### 10.3 Performance Considerations

**Batch Tracking**:
- Progress every 100 records during uploads
- Time tracking every 5 minutes during matching
- Allows estimation of completion time

**Indexing Strategy**:
- Created on demand: `index_check(collection, identifiers)`
- Uses composite indexes: `[(key, pymongo.ASCENDING), ...]`

**Caching Strategy**:
- Full data cached to CSV/JSON locally
- Avoids repeated network requests
- User prompted before using old cache

### 10.4 Unusual Design Decisions

1. **Global Variables in utils.py**: Initialized at module import time
   - Pro: Simple access throughout
   - Con: Requires config.toml to exist for import to succeed

2. **Star Imports in retrieve.py**: `from scripts.utils import *`
   - Makes all utils functions available without prefix
   - Works because interface.py imports from same package

3. **Manual Field Mapping**: Rather than ORM or auto-detection
   - Pro: Explicit control over data transformation
   - Pro: Handles heterogeneous sources
   - Con: Requires human maintenance for each registry

4. **Lazy Imports**: Country modules imported only when selected
   - Pro: Fast startup, only load needed code
   - Con: Import errors only caught at runtime

## 11. DEVELOPER WORKFLOW AND ADDING NEW REGISTRIES

### To Add a New Registry:

1. **Create directory**: `/scripts/NewCountry/`
2. **Create `retrieve.py`** with:
   - Global variables (API URL, registry name, headers)
   - `retrieve_data(folder)` function
   - `run_everything(folder)` function
3. **Create `mapping.json`** with field mappings
4. **Update `interface.py`**:
   - Add to `retrieval_options` menu
   - Add to `all_options` range
   - Add elif branch importing and calling your retrieve.py
5. **Create schema fields** in `/schemas/entity.json` if needed
6. **Add legal notice** to `run_everything()` if required
7. **Test** using Status Check and Keyword Match Assist

### Code Review Points:

- Are all unique identifiers correctly mapped?
- Are date formats handled (see mapping.json format field)?
- Is encoding handled for source data?
- Is cache cleanup done properly?
- Are legal notices included?
- Are exceptional cases handled (orphans, duplicates)?

## 12. SUMMARY TABLE: REGISTRIES

| Country | Type | Updates | Entities | Filings | Caching | Special Needs |
|---------|------|---------|----------|---------|---------|--------------|
| Australia | CSV | Periodic | YES | NO | CSV cache | Encoding handling |
| EnglandWales | JSON (zipped) | Periodic | YES | YES | JSON cache | Dual datasets |
| NewZealand | CSV (OData) | Live | YES | NO | CSV cache | Low memory handling |
| UnitedStates | CSV+Metadata | Periodic | YES | YES | CSV cache | Multi-region concat, web scrape |

## 13. CRITICAL PATHS

**Critical Path 1 - Data Retrieval**:
interface.py → country/retrieve.py → retrieve_data() → send_all_to_mongodb() → MongoDB

**Critical Path 2 - Filing Matching**:
interface.py → utils.match_filing_all() → match_filing() → MongoDB update

**Critical Path 3 - Status**:
interface.py → utils.status_check() → MongoDB aggregations → terminal output

