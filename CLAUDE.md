# CLAUDE.md - AI Assistant Guide for Regeindary

## Project Overview

**Regeindary** is a standardized registry data aggregation tool that imports publicly-available data from heterogeneous civil society and organizational registries (nonprofits, charities, NGOs, etc.) and stores them in a unified MongoDB database.

**Key Concept**: An "entity" (organization) may be linked to multiple "filings" (annual reports, tax returns, etc.)

**Current Status**: Supports 4 registries (Australia, England & Wales, New Zealand, United States) with ~2,500 lines of Python code.

---

## Strategic Position & Competitive Landscape

### Market Context

Regeindary operates in a space with several existing solutions:

| Solution | Coverage | Open Source | Cost | Self-Hosted |
|----------|----------|-------------|------|-------------|
| **GlobalGiving Atlas** | 9.6M orgs, 75 countries | No | Paid license | No |
| **Better Giving Studio** | 8.5M orgs, 80 countries | No | Paid tiers | No |
| **Candid/GuideStar** | 1.8M US orgs | No | $6,000+/year | No |
| **CharityBase** | 350K UK orgs | Yes | Free | Yes |
| **Nonprofit Open Data Collective** | US IRS 990 data | Yes | Free | Yes |
| **Regeindary** | 4 countries | Yes | Free | Yes |

### Regeindary's Unique Position

Regeindary fills a gap that no other solution addresses: **open source + multi-country + self-hosted**.

- **CharityBase** is open source but UK-only
- **Nonprofit Open Data Collective** is open source but US-only
- **GlobalGiving Atlas** is multi-country but proprietary and paid

### Competitive Advantages

1. **Open source / self-hosted** - Full data control, no API costs or rate limits
2. **Entity-to-filing relationships** - The `match_filing()` linking is a differentiating feature most APIs don't provide
3. **Raw data access** - "Original Data" preservation enables custom analysis
4. **Schema flexibility** - Researchers can extend for specific needs

### Strategic Guidance

**Scale is not the goal.** GlobalGiving Atlas has 9.6M records across 75 countries. Regeindary's value is **depth over breadth**:

- Focus on well-maintained registries rather than maximum country count
- Prioritize data quality and entity-filing relationships
- Optimize for research use cases (Nipwiss) rather than donation verification

**Recommended priorities:**
1. Maintain current 4 registries with high data quality
2. Complete Ireland support (already started)
3. Consider Canada (complements US coverage, good data availability)
4. Avoid duplicating CharityBase's UK work

---

## Future Vision: Shadow Registry for Invisible Organizations

### The Problem

Regeindary currently answers: **"What organizations exist according to governments?"**

But millions of civil society organizations are invisible because:
- **Weak state capacity** - Government doesn't maintain registries (many Global South nations)
- **Hostile governments** - Registration = surveillance/persecution (authoritarian regimes)
- **Informal civil society** - Community groups that never formalized
- **Conflict zones** - No functioning registration system exists
- **Indigenous organizations** - Operate outside Western nonprofit frameworks

### The Vision

A future tool (separate from Nipwiss) could use Regeindary's schema as infrastructure to make these invisible organizations visible to researchers and funders.

**Two-layer model:**
```
Layer 1: Regeindary (unchanged)
├── Official registry data
├── High confidence, government-verified
└── Current functionality

Layer 2: "Shadow Registry" (future tool)
├── Self-reported organizations
├── Linkage-inferred verification
├── Graduated trust scores
└── Interoperable with Layer 1 via shared schema
```

### Verification Without Government Registries

The key insight: **Nipwiss linkages can provide transitive trust**.

If Nipwiss web scraping detects that an unregistered organization:
- Is listed as a partner on Oxfam UK's website (a Regeindary-verified org)
- Received a grant from Ford Foundation (verifiable)
- Has board members who serve on registered charities
- Is cited in academic research or reputable journalism

...then those linkages bestow credibility without requiring government registration.

### Proposed Data Model Extension

```javascript
// Potential schema additions for linkage-verified orgs
{
  entityName: "Example Grassroots Network",
  verificationStatus: "linkage_inferred",  // vs "government_registry"

  linkages: [
    {
      linkedEntity: ObjectId("..."),        // Ford Foundation in Regeindary
      linkageType: "grant_recipient",
      evidence: "https://fordfoundation.org/grants/...",
      detectedDate: "2024-03-15",
      confidence: 0.9
    },
    {
      linkedEntity: ObjectId("..."),        // Oxfam UK
      linkageType: "listed_partner",
      evidence: "https://oxfam.org.uk/partners/...",
      detectedDate: "2024-03-15",
      confidence: 0.85
    }
  ],

  trustScore: 0.87  // Computed from linkages
}
```

### Value Proposition

**For researchers:**
- Study civil society where official data doesn't exist
- Compare formal vs. informal nonprofit sectors
- Track organizations that later formalize

**For funders:**
- Discover grassroots organizations invisible to traditional databases
- Due diligence signals for orgs without official papers
- Direct funding to underserved regions

**For the organizations themselves:**
- Visibility to international funders without government blessing
- Legitimacy signal through verified relationships
- Network discovery (find similar organizations)

### Implementation Considerations

This would be a **separate project** that shares Regeindary's schema but requires:
- Privacy protections (critical for hostile-state contexts)
- User-facing submission interface
- Trust/reputation system design
- Clear separation from government-verified data

**Regeindary's role:** Schema infrastructure proving that heterogeneous organization data can be standardized. The same schema could accommodate linkage-verified data with appropriate metadata.

### Why This Matters

No existing solution provides open, self-hostable infrastructure for discovering and verifying civil society organizations outside formal government registries. Commercial APIs like GlobalGiving Atlas focus on donation routing ("is this a valid charity?"), not research discovery ("what organizations exist in this space?").

The combination of:
1. **Regeindary** (official registry aggregation)
2. **Nipwiss** (web scraping and linkage detection)
3. **Shadow Registry** (future - linkage-inferred verification)

...could create a unique research infrastructure for studying global civil society comprehensively.

---

## MongoDB Model Interdependency with Nipwiss

### Overview

**Critical**: Regeindary's MongoDB database serves as a **shared data contract** between Regeindary and [Nipwiss](https://github.com/KalebNyquist/nipwiss) (a private repository for non-profit web scraping and data aggregation).

**Relationship**:
- **Regeindary**: Data ingestion layer - imports and standardizes registry data
- **Nipwiss**: Data consumption layer - uses the standardized MongoDB for web scraping and analysis
- **MongoDB**: Shared interface - acts as a versioned API contract between the two systems

### Critical Architectural Constraints

Because Nipwiss depends on Regeindary's MongoDB schema, the following are **breaking change considerations**:

#### 1. Collection Structure (CRITICAL)
The three-collection model is foundational to Nipwiss:
- `registries` - Registry metadata and import tracking
- `organizations` - Standardized entity records
- `filings` - Annual reports and financial data

**⚠️ Do not rename or restructure these collections without coordinating with Nipwiss**

#### 2. Required Field Names (CRITICAL)
These camelCase field names form the data contract and **must remain stable**:

**organizations collection**:
- `entityId` - Public registry identifier
- `entityName` - Organization name
- `entityIndex` - Internal unique identifier
- `registryID` - MongoDB ObjectId linking to registries collection
- `registryName` - Human-readable registry name
- `websiteUrl` - Official organization URL
- `registeredDate` - Date entered into registry
- `establishedDate` - Date organization was founded

**filings collection**:
- `filingId` - Public filing identifier
- `entityId` - Links to parent organization
- `entityId_mongo` - MongoDB ObjectId after matching (populated by `match_filing()`)
- `registryID` - MongoDB ObjectId linking to registries collection
- `startDate` - Fiscal period start
- `endDate` - Fiscal period end
- `recordDate` - Filing submission date
- `totalIncome` - Financial data
- `totalExpenditures` - Financial data

**registries collection**:
- `_id` - MongoDB ObjectId (referenced as `registryID` in other collections)
- `name` - Registry name (referenced as `registryName` in other collections)
- `source` - Data source URL
- `download_completion` - Import timestamp

#### 3. Data Type Contracts (CRITICAL)
- **Dates**: ISO 8601 strings (YYYY-MM-DD) - not Date objects
- **Numbers**: Numeric types (int/float) - no currency symbols or strings
- **IDs**: String type - various formats per registry
- **URLs**: Full HTTP/HTTPS strings
- **ObjectIds**: MongoDB ObjectId type for `_id`, `registryID`, `entityId_mongo`

#### 4. Field Naming Conventions (CRITICAL)
- **Schema fields**: `camelCase` (e.g., `entityId`, `entityName`)
- **Collection names**: `lowercase_plural` (e.g., `organizations`, `filings`)
- **Metadata fields**: `snake_case` (e.g., `download_completion`, `Original Data`)

#### 5. Entity-Filing Relationship (CRITICAL)
The relationship created by `match_filing()` and `run_all_match_filings()` is essential:
- Filings must link to organizations via `entityId_mongo` field
- This field is populated after matching process completes
- Orphan filings auto-create placeholder organizations
- Relationship enables Nipwiss to traverse entity → filings

### Safe vs Breaking Changes

#### ✅ Safe Changes (Non-Breaking)
- **Adding new fields** to existing documents (Nipwiss will ignore unknown fields)
- **Adding new mappings** in mapping.json files
- **Adding new registries** (new data sources)
- **Performance optimizations** to utils.py functions
- **Adding indexes** for query performance
- **Enriching "Original Data"** nested object
- **Adding new schemas** (e.g., `people.json`)

#### ⚠️ Breaking Changes (Require Nipwiss Coordination)
- **Renaming existing fields** (e.g., `entityId` → `organizationId`)
- **Changing data types** (e.g., date strings → Date objects)
- **Removing fields** that Nipwiss depends on
- **Restructuring collections** (e.g., merging organizations + filings)
- **Changing collection names** (e.g., `organizations` → `entities`)
- **Modifying `entityId_mongo` relationship** structure
- **Changing date format** from ISO 8601 strings

### Versioning Strategy

Currently there is **no formal schema versioning**. When making changes:

1. **Before breaking changes**:
   - Document the change in this CLAUDE.md file
   - Consider impact on Nipwiss data queries
   - Coordinate with Nipwiss development
   - Test both systems with the change

2. **Migration path** (if needed):
   - Maintain old fields during transition period
   - Add new fields alongside old ones
   - Deprecate rather than delete
   - Use `Original Data` for fallback values

3. **Future consideration**: Add schema version field to documents
   ```python
   {
       "_schema_version": "1.0",
       "entityId": "...",
       # ... rest of fields
   }
   ```

### Testing Impact on Nipwiss

When modifying Regeindary's MongoDB model:

#### Required Tests
1. **Field presence**: Ensure all critical fields still exist
2. **Data type validation**: Verify types match contract (strings, numbers, etc.)
3. **Relationship integrity**: Test entity-filing links via `entityId_mongo`
4. **Collection queries**: Verify queries still return expected structure
5. **Index performance**: Ensure indexes support common Nipwiss queries

#### Testing Workflow
1. Run Regeindary import with changes
2. Use `status_check()` to verify data completeness
3. Use `get_random_entity()` to inspect field structure
4. Query MongoDB directly to verify schema:
   ```javascript
   // In MongoDB shell
   db.organizations.findOne()
   db.filings.findOne()
   db.registries.findOne()
   ```
5. Test Nipwiss queries against updated database
6. Verify no missing fields or type errors in Nipwiss

### Documentation Requirements

When making schema changes, update:
1. **This section** of CLAUDE.md - Document what changed and why
2. **schemas/*.json** - Update JSON Schema definitions
3. **mapping.json files** - Update field mappings if needed
4. **Nipwiss documentation** - Coordinate updates to Nipwiss CLAUDE.md if breaking changes
5. **Git commit messages** - Clearly indicate schema changes

### Key Indexes Used by Nipwiss

These indexes are created by Regeindary and relied upon by Nipwiss:

**organizations collection**:
- `(registryID, entityId)` - Primary lookup index
- `(registryID, entityIndex)` - Alternative lookup (more reliable for some registries)

**filings collection**:
- `(registryID, entityId)` - Links filings to organizations
- `entityId_mongo` - Traverses to matched organization

**Performance note**: These indexes are critical for Nipwiss query performance at scale (500k+ records).

### Shared Schemas as Contract

The JSON Schema files in `/schemas` directory serve as the formal contract:
- **schemas/entity.json** - Defines valid organization fields
- **schemas/filing.json** - Defines valid filing fields

**Best practice**: When adding new standardized fields:
1. Update the JSON Schema first
2. Update mapping.json files to use new fields
3. Test with sample data
4. Document in both Regeindary and Nipwiss CLAUDE.md files

### AI Assistant Guidelines for Schema Changes

When working on Regeindary and considering schema changes:

#### Always Ask
- "Will this change affect how Nipwiss queries the data?"
- "Are we renaming or removing any existing fields?"
- "Are we changing the data type of existing fields?"
- "Does this affect the entity-filing relationship?"

#### Before Implementing
- Check if change is breaking vs. non-breaking (see lists above)
- Review current schema in `schemas/*.json`
- Check how field is used in `mapping.json` files
- Consider backwards compatibility

#### When Adding Features
- Prefer additive changes (new fields) over modifications (renamed fields)
- Document new fields in JSON Schema
- Add to mapping.json for relevant registries
- Update this section of CLAUDE.md

#### Red Flags (Breaking Changes)
- Renaming camelCase schema fields
- Changing collection names
- Modifying relationship structure (`entityId_mongo`)
- Changing date/number formats
- Removing fields used in schemas

---

## Architecture & Data Flow

### High-Level Flow
```
User Selection (interface.py)
    ↓
Country Module (retrieve.py)
    ↓
retrieve_data() → Download/Cache → Parse to list of dicts
    ↓
Load mapping.json → Apply field transformations
    ↓
send_all_to_mongodb() → Insert to MongoDB
    ↓
(Optional) match_filing() → Link filings to organizations
    ↓
MongoDB Collections: registries, organizations, filings
```

### Core Components

1. **interface.py** (102 lines) - CLI entry point with 6 operations
2. **utils.py** (426 lines) - All MongoDB operations and business logic
3. **[Country]/retrieve.py** - Country-specific data retrieval
4. **[Country]/mapping.json** - Field name translations (origin → target)
5. **schemas/*.json** - JSON Schema definitions for standardized fields
6. **config.toml** - MongoDB connection configuration

---

## Directory Structure

```
/home/user/regeindary/
├── scripts/
│   ├── interface.py          # CLI menu
│   ├── utils.py              # Database ops & utilities
│   ├── config.toml           # MongoDB config
│   ├── Australia/
│   │   ├── retrieve.py       # Data retrieval logic
│   │   ├── metadata.json     # Registry metadata (name, URLs, legal notices)
│   │   └── mapping.json      # Field transformations
│   ├── EnglandWales/
│   │   ├── retrieve.py
│   │   ├── metadata.json
│   │   └── mapping.json
│   ├── NewZealand/
│   │   ├── retrieve.py
│   │   ├── metadata.json
│   │   └── mapping.json
│   ├── UnitedStates/
│   │   ├── retrieve.py
│   │   ├── metadata.json
│   │   └── mapping.json
│   └── Ireland/
│       ├── retrieve.py
│       ├── metadata.json
│       └── mapping.json
└── schemas/
    ├── entity.json           # Organization schema
    └── filing.json           # Filing/report schema
```

---

## Code Conventions & Patterns

### Naming Conventions
- **Global constants**: `UPPER_SNAKE_CASE` (e.g., `api_retrieval_point`, `registry_name`)
- **Functions**: `snake_case` (e.g., `retrieve_data`, `send_to_mongodb`)
- **Schema fields**: `camelCase` (e.g., `entityId`, `entityName`, `registryID`)
- **Collections**: `lowercase_plural` (e.g., `organizations`, `filings`, `registries`)

### Code Style
- 4-space indentation
- f-strings and `.format()` for string formatting
- TODO comments: `# - [ ]` (checkbox format)
- Status messages with emojis: ✔, ✅, ⬜, ⚠️
- Progress on same line: `print(..., end="\r")`
- Clear section separators: `# Globals`, `# Functions`
- Graceful interrupt handling: Try/except for Ctrl+C

### Import Patterns
- **utils.py**: Standard imports only
- **Country modules**: `from scripts.utils import *` (star imports for convenience)
- **interface.py**: Lazy imports (only load selected country modules)

---

## MongoDB Schema

### Three Collections

1. **registries** (metadata tracking)
   - `_id`: MongoDB ObjectId
   - `name`: Registry name (e.g., "Australia")
   - `source`: URL or description
   - `legalNotices`: Array of legal notice objects (stored once per registry, not duplicated in records)
   - `download_completion`: Timestamp when import completed

2. **organizations** (standardized entities)
   - **Standard fields**: `entityId`, `entityName`, `websiteUrl`, `registeredDate`, `establishedDate`, etc.
   - **Added fields**: `registryID`, `registryName`, `Original Data`
   - **Indexes**: `(registryID, entityId)`, `(registryID, entityIndex)`
   - **Note**: `legalNotices` moved to registry level (see issue #25)

3. **filings** (annual reports)
   - **Standard fields**: `filingId`, `startDate`, `endDate`, `totalIncome`, `totalExpenditures`, etc.
   - **Added fields**: `registryID`, `entityId_mongo` (set after matching)
   - **Indexes**: `(registryID, entityId)`

### Schema Field Types
- Dates: ISO 8601 strings (YYYY-MM-DD)
- Numbers: Stored as int/float (no currency symbols)
- IDs: Strings (various formats per registry)
- URLs: Full HTTP/HTTPS strings
- Original Data: Preserved as nested object

---

## Key Functions (utils.py)

### Database Operations
- `get_config()` - Parse config.toml
- `get_mongo_dbs()` - Get collection handles
- `send_to_mongodb(record, collection, mapping, meta_id)` - Insert single record
- `send_all_to_mongodb(records, collection, mapping, meta_id)` - Batch insert with progress
- `meta_check(name, source)` - Get/create registry metadata
- `completion_timestamp(meta_id)` - Mark import complete

### Incremental Update Operations (NEW)
- `preview_new_records(records, mapping, static, collection, unique_field)` - Analyze incoming records to identify new vs existing
- `send_new_to_mongodb(records, mapping, static, collection, unique_field)` - Insert only new records, skip duplicates
- `upsert_all_to_mongodb(records, mapping, static, collection, unique_field)` - Update existing + insert new records
- `delete_old_records(registry_id, collection)` - Now supports incremental update option

### Entity-Filing Matching
- `match_filing(filing, collection)` - Link filing to organization
- `run_all_match_filings()` - Process all unmatched filings (optimized for 500k+ records)
- `create_organization_from_orphan_filing(filing)` - Auto-create org for orphan filing

### Registry Metadata Operations
- `load_registry_metadata(folder)` - Load metadata.json for a registry
- `register_registry(metadata, collection)` - Create/update registry with legal notices at registry level
- `get_registry_legal_notices(registry_id)` - Retrieve legal notices for a registry (for Nipwiss)
- `display_legal_notices(legal_notices)` - Print legal notices to console

### Utilities
- `check_for_cache()` - Prompt user about cached data
- `retrieve_mapping(folder)` - Load mapping.json
- `status_check()` - Display database statistics
- `keyword_match_assist()` - Show field mapping coverage
- `get_random_entity()` - Display random org for inspection

---

## Standard Registry Module Pattern

Every `[Country]/retrieve.py` follows this structure:

```python
# Imports
from scripts.utils import *
import pandas as pd
import requests
# etc.

# Functions
def retrieve_data(folder, metadata):
    """Download/cache data and return list of dicts"""
    api_url = metadata['api_url']  # Get URL from metadata.json
    # 1. Check for cache
    # 2. Download if needed
    # 3. Parse to list of dicts
    # 4. Return data

def run_everything(folder):
    """Main orchestration function"""
    # 1. Load metadata from metadata.json
    metadata = load_registry_metadata(folder)
    registry_name = metadata['name']

    # 2. Display legal notices
    display_legal_notices(metadata.get('legal_notices', []))

    # 3. Call retrieve_data()
    raw_dicts = retrieve_data(folder, metadata)

    # 4. Load mapping
    custom_mapping = retrieve_mapping(folder)

    # 5. Register registry (stores legal_notices at registry level)
    meta_id, decision = register_registry(metadata)

    # 6. Upload data (legalNotices NOT in static_amendment)
    static_amendment = {
        "registryName": registry_name,
        "registryID": meta_id
    }
    send_all_to_mongodb(raw_dicts, custom_mapping, static_amendment)

    # 7. Mark completion
    completion_timestamp(meta_id)
```

### metadata.json Format

Each registry has a `metadata.json` file containing:

```json
{
  "name": "Country - Registry Name",
  "source_url": "https://data-source-page.example.com",
  "api_url": "https://api.example.com/data.csv",
  "headers": {
    "user-agent": "Mozilla/5.0..."
  },
  "collections": ["organizations"],
  "legal_notices": [
    {
      "title": "License Name",
      "description": "Full license text...",
      "url": "https://license-url.example.com"
    }
  ]
}
```

**Key benefit**: Legal notices are stored once in the `registries` collection, not duplicated in every organization/filing record.

---

## Field Mapping System

**mapping.json** format:
```json
[
  {"origin": "Source_Field_Name", "target": "standardizedFieldName"},
  {"origin": "Date_Field", "target": "establishedDate", "format": "DD/MM/YYYY"},
  {"origin": "Numeric_Field", "target": "totalIncome"}
]
```

**Important**:
- `origin` = field name in source data
- `target` = field name in standardized schema
- Optional `format` for date parsing
- Unmapped fields stored in "Original Data"
- See `schemas/entity.json` and `schemas/filing.json` for available target fields

---

## Registry-Specific Details

### Australia
- **Source**: CSV from data.gov.au
- **Data**: Entities only (no filings)
- **Fields**: 4 basic fields
- **Quirks**: Encoding handling required

### England & Wales
- **Source**: JSON from Azure (zipped)
- **Data**: Both entities and filings
- **Fields**: 10 fields
- **Quirks**:
  - Dual dataset (charities + filings)
  - UTF-8-sig encoding
  - Better matching with `entityIndex` than `entityId`

### New Zealand
- **Source**: CSV from OData API
- **Data**: Entities only (no filings)
- **Fields**: 5 fields
- **Quirks**:
  - Requires `low_memory=False` for pandas
  - Legal anti-spam notice required (Unsolicited Electronic Messages Act 2007)

### United States
- **Source**: 4 regional CSVs + metadata
- **Data**: Both entities and filings
- **Fields**: 11 fields
- **Quirks**:
  - Multi-region concatenation required
  - ID padding with `.rjust(9, '0')`
  - Uses tqdm progress bars
  - Windows-specific paths in some sections
  - Largest dataset (500k+ records)

---

## Development Workflows

### Adding a New Registry

1. **Create directory**: `scripts/NewCountry/`

2. **Create metadata.json** with registry configuration:
   ```json
   {
     "name": "NewCountry - Registry Name",
     "source_url": "https://registry-homepage.example.com",
     "api_url": "https://api.example.com/data.csv",
     "headers": {
       "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)..."
     },
     "collections": ["organizations"],
     "legal_notices": [
       {
         "title": "License Name",
         "description": "License terms...",
         "url": "https://license.example.com"
       }
     ]
   }
   ```

3. **Create retrieve.py** following standard pattern:
   ```python
   from scripts.utils import *

   def retrieve_data(folder, metadata):
       # Implementation using metadata['api_url']
       return data_as_list_of_dicts

   def run_everything(folder):
       metadata = load_registry_metadata(folder)
       display_legal_notices(metadata.get('legal_notices', []))

       data = retrieve_data(folder, metadata)
       mapping = retrieve_mapping(folder)
       meta_id, _ = register_registry(metadata)

       static = {"registryName": metadata['name'], "registryID": meta_id}
       send_all_to_mongodb(data, mapping, static)
       completion_timestamp(meta_id)
   ```

4. **Create mapping.json** with field mappings

5. **Update interface.py** to add menu option

6. **Test** with small dataset first

7. **Run** full import and verify with status_check()

### Testing Changes

1. **Status Check** (`interface.py` option 1):
   - Shows record counts, timestamps, coverage %
   - Quick validation that data imported correctly

2. **Keyword Match Assist** (option 3):
   - Shows which schema fields are mapped/unmapped
   - Helps identify missing mappings

3. **Display Random Entity** (option 5):
   - Inspects actual data with mappings applied
   - Validates data quality and transformation

### Modifying Existing Registry

1. **Check current mapping**: Review `[Country]/mapping.json`
2. **Update mapping**: Add/modify field mappings
3. **Re-import data**: Run retrieve option, allow overwrite
4. **Verify**: Use status_check() and get_random_entity()

### Incremental Updates (Annual Registry Updates) ⭐ NEW

**Use Case**: Adding new records from annual registry releases without losing old data

When you run a retrieval and existing records are found, you'll see:
```
Found 10,234 existing records. Choose an option:
  [y] Delete all old records and insert new data
  [i] Incremental update (insert only new records)
  [n] Keep old records (may cause duplicate errors)
  [s] Skip upload entirely
```

#### Option [i]: Incremental Update Workflow

1. **Preview Phase**: System analyzes incoming data
   ```
   Analyzing new data...
     ✔ Found 10,500 records in source data
     ✔ Found 10,234 existing records in MongoDB
     ✔ Categorizing records... ✔

   ======================================================================
                            PREVIEW RESULTS
   ======================================================================
     • 266 new records (not in database)
     • 10,234 duplicate records (already exist)
   ======================================================================
   ```

2. **Action Menu**:
   ```
   What would you like to do?
     [1] Insert only new records (skip duplicates)
     [2] Show sample of new records
     [3] Cancel operation
   ```

3. **Insert**: Only new records are added to MongoDB (old records preserved)

#### How Duplicate Detection Works

- **Organizations**: Matched on `(registryID, entityId)`
- **Filings**: Matched on `(registryID, filingId)` or `(registryID, filingIndex)`
- Existing records remain unchanged
- Only truly new records are inserted

#### Example: Australia Registry Update

```python
def run_everything(folder=""):
    data = retrieve_data(folder)
    mapping = retrieve_mapping(folder)
    meta_id, decision = meta_check(registry_name, source_url)

    static = {"registryID": meta_id, "registryName": registry_name}

    if decision == 'i':  # Incremental update
        send_new_to_mongodb(data, mapping, static,
                           collection='organizations',
                           unique_field='entityId')
    # ... other options
```

#### Advanced: Upsert Mode (Not in UI Yet)

For updating existing records + inserting new ones:
```python
upsert_all_to_mongodb(data, mapping, static,
                     collection='organizations',
                     unique_field='entityId')
```

**Benefits**:
- ✅ No data loss (old records preserved)
- ✅ Efficient (only insert what's new)
- ✅ Transparent (preview before committing)
- ✅ Safe (cancel anytime before insertion)

### Matching Filings to Organizations

- Run option 4: "Match Filings with Entities"
- Creates indexes for performance
- Finds unmatched filings and links to organizations
- Auto-creates organizations from orphan filings if no match
- Optimized for large datasets (500k+ records)

---

## Important Quirks & Gotchas

### Global State
- **MongoDB connection initialized at import time** in utils.py
- Requires `config.toml` to exist before importing
- Connection stored in global variables: `organizations_collection`, `filings_collection`, etc.

### Caching Strategy
- First run: downloads and saves cache locally
- Subsequent runs: prompts user to use cache or redownload
- Allows iterative testing without repeated network requests
- **AI Note**: When modifying retrieval logic, suggest clearing cache

### Orphan Filings
- Filings without matching organizations auto-create placeholder orgs
- Includes breadcrumb metadata for tracing
- Prevents data loss but may need manual review

### ID Formatting Issues
- **US Registry**: Requires `.rjust(9, '0')` for EIN padding
- **EnglandWales**: `entityIndex` more reliable than `entityId` for matching
- Always test matching logic after changes

### Performance Considerations
- `run_all_match_filings()` recently optimized for speed
- Uses batch processing and progress tracking
- Creates indexes before matching for performance
- Handles 500k+ records efficiently

### Windows vs Unix Paths
- Some US code uses backslash paths
- May need adjustment for cross-platform compatibility

---

## Configuration

### config.toml
```toml
mongo_path = "mongodb://127.0.0.1:27017/"
database_name = "regeindary"
organization_collection = "organizations"
filings_collection = "filings"
meta_collection = "registries"
```

**AI Note**: When helping with MongoDB connection issues, check this file first.

---

## Dependencies

### Required Python Version
- **Python 3.11+** (requires `tomllib` module)

### Core Packages
- `pymongo` - MongoDB driver
- `pandas` - CSV/data manipulation
- `requests` - HTTP requests
- `beautifulsoup4` - HTML parsing (US web scraping)
- `tqdm` - Progress bars (US only)
- `zipfile-deflate64` - ZIP extraction (US only)

### External Services
- MongoDB locally (v8.0.0+)
- Various data APIs (per registry)

---

## Git Workflow

### Current Branch
- Working on: `claude/claude-md-mhzmeadr19qwj39k-01Uwww7aCvRp8GNwHPDEKp5K`
- **Always push to this branch**

### Commit Messages
- Follow existing patterns (see git log)
- Examples:
  - "Improved batch monitoring + termination speed for run_all_match_filings()"
  - "Minor improvements during match filings process"

### Recent Optimizations (from git history)
- Improved `run_all_match_filings()` speed
- Better batch monitoring and termination
- Performance improvements for large datasets

---

## Common AI Assistant Tasks

### "Add support for new registry"
1. Research data source format and API
2. Create `scripts/[Country]/` directory
3. Implement `retrieve.py` with standard pattern
4. Create `mapping.json` with field mappings
5. Update `interface.py` menu
6. Test with small dataset
7. Document in README.md

### "Fix data import issue"
1. Check error message context
2. Verify MongoDB connection (config.toml)
3. Check mapping.json for field mismatches
4. Validate source data format hasn't changed
5. Test with smaller dataset
6. Use status_check() to verify fix

### "Optimize performance"
1. Profile with large dataset
2. Check index usage in MongoDB
3. Consider batch processing improvements
4. Look at recent optimizations in git history
5. Test with real datasets (US has 500k+ records)

### "Add new standardized field"
1. Update `schemas/entity.json` or `schemas/filing.json`
2. Update relevant `mapping.json` files
3. Test with existing data
4. May need to re-import data for full coverage

### "Debug matching issues"
1. Use `keyword_match_assist()` to see coverage
2. Check `get_random_entity()` for data quality
3. Verify ID formatting (padding, case, etc.)
4. Test `match_filing()` with specific examples
5. Check for orphan filings created

---

## Testing & Validation

### Built-in Tools
1. **Status Check** - Counts, timestamps, coverage percentages
2. **Keyword Match Assist** - Shows mapped vs unmapped schema fields
3. **Display Random Entity** - Inspect actual data with mappings

### Manual Testing Checklist
- [ ] Data downloads successfully
- [ ] Cache mechanism works
- [ ] Field mappings apply correctly
- [ ] All expected fields populated
- [ ] MongoDB documents valid
- [ ] Filings match to correct organizations
- [ ] No orphan filings (or expected number)
- [ ] Performance acceptable for dataset size

---

## Additional Resources

- **README.md** - User-facing documentation
- **schemas/entity.json** - Organization field definitions
- **schemas/filing.json** - Filing field definitions
- Each `mapping.json` - See working examples of field mappings

---

## AI Assistant Guidelines

### When Analyzing Code
- Check global state in utils.py first
- Understand MongoDB connection lifecycle
- Review existing registry patterns before suggesting changes
- Consider caching implications

### When Making Changes
- Follow established naming conventions
- Maintain standard registry module pattern
- Test with small dataset before full import
- Update mapping.json alongside retrieve.py changes
- Document any new quirks or gotchas

### When Helping Debug
- Ask about MongoDB connection status
- Check config.toml exists and is valid
- Verify Python version (3.11+ required)
- Review recent git history for related changes
- Use built-in testing tools (status_check, etc.)

### When Adding Features
- Prefer extending existing patterns over new paradigms
- Maintain backward compatibility with existing registries
- Document in this CLAUDE.md file
- Consider performance impact (500k+ record scale)
- Update README.md if user-facing

---

## Quick Reference Commands

```bash
# Working directory
cd /home/user/regeindary/scripts

# Run interface
python interface.py

# Common operations
# [1] Status Check
# [2] Retrieve Registries → Select country
# [4] Match Filings with Entities
# [5] Display Random Entity
```

---

**Last Updated**: 2025-11-22
**Codebase Size**: ~2,500 lines of Python
**Registries Supported**: 4 (Australia, England & Wales, New Zealand, United States)
**New Features**: Incremental updates for annual registry releases
**Future Vision**: Shadow Registry for linkage-verified invisible organizations
