# Regeindary Development Patterns and Conventions

## 1. FILE STRUCTURE PATTERNS

### 1.1 Standard Country retrieve.py Structure

Every country-specific `retrieve.py` follows this exact template:

```python
# SECTION 1: IMPORTS
import os
import sys
import pandas as pd
from scripts.utils import *

# Add path for consistency
project_root = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_root)
if parent_dir not in sys.path:
    print("Adding root")
    sys.path.append(parent_dir)

# SECTION 2: GLOBALS (API URLs, metadata, etc.)
api_retrieval_point = "https://api.example.com/data"
source_url = 'https://example.com/registry'
headers = {"user-agent": "Mozilla/5.0 ..."}
registry_name = "Country Name - Registry Full Name"
global mongo_regeindary

# SECTION 3: HELPER FUNCTIONS (if any)
def helper_function():
    pass

# SECTION 4: MAIN FUNCTIONS
def retrieve_data(folder):
    """Download and parse data from source"""
    # Implementation here
    return raw_dicts

def run_everything(folder=""):
    """Main orchestration function"""
    # Legal notice
    # Get data
    # Get mapping
    # Meta check
    # Send to MongoDB
    # Timestamp
    return final_results

# SECTION 5: EXECUTION
if __name__ == '__main__':
    run_everything()
```

### 1.2 Mapping.json Structure

```json
[
  {
    "origin": "Source_Column_Name",
    "target": "standardizedFieldName"
  },
  {
    "origin": "Date_Field",
    "target": "establishedDate",
    "format": "DD/MM/YYYY"
  }
]
```

**Rules**:
- `origin`: Exact field name from source data
- `target`: Field name from entity.json or filing.json schema
- `format`: Optional, for date parsing hints (for future use)

## 2. NAMING CONVENTIONS

### 2.1 Python Variable Names

| Category | Pattern | Example |
|----------|---------|---------|
| Global constants | UPPER_SNAKE_CASE | `api_retrieval_point`, `registry_name` |
| Functions | snake_case | `retrieve_data()`, `send_to_mongodb()` |
| Local variables | snake_case | `response_dicts`, `meta_id` |
| MongoDB ObjectId | _id suffix | `registry_id` (local var), stored as ObjectId |
| Collections | lowercase plural | `organizations`, `filings`, `registries` |

### 2.2 MongoDB Field Names

**Standard camelCase pattern**:

```javascript
// Identity fields
entityId                 // Public registry ID
entityName              // Organization name
entityIndex             // Internal registry index
subsidiaryId            // Nested entity identifier

// Date fields (all ISO format in code)
registeredDate          // When entered registry
establishedDate         // When founded
startDate               // Fiscal period start
endDate                 // Fiscal period end
recordDate              // Filing submission date

// Relationship fields
registryID              // Foreign key to registries._id
registryName            // Source registry name
entityId_mongo          // Link to organizations._id (for filings)

// Financial fields
totalIncome             // Total revenue
totalExpenditures       // Total expenses

// Metadata fields
legalNotices            // Array of license info
Original Data           // Unmodified source record
sourceData              // Metadata about retrieval
```

### 2.3 Function Parameter Patterns

**retrieve_data() signature**:
```python
def retrieve_data(folder):
    # folder is the country directory path, e.g., "Australia/"
    # Returns: list of dicts representing raw records
```

**run_everything() signature**:
```python
def run_everything(folder=""):
    # folder defaults to empty string
    # Called from interface.py as: retrieve.run_everything("Australia/")
    # Returns: dict of results from send_all_to_mongodb
```

## 3. CODING PATTERNS

### 3.1 Caching Pattern

Every country implementation uses this pattern:

```python
def retrieve_data(folder):
    cached = check_for_cache(folder, label="entities", suffix="csv")
    
    if cached:
        print(" Skipping download: using cached copy")
        response_df = pd.read_csv(f"{folder}cache_entities.csv")
    elif cached is False:
        print(" Downloading fresh data")
        response_df = pd.read_csv(api_url)
        response_df.to_csv(f"{folder}cache_entities.csv")
    else:
        raise Exception
    
    response_dicts = response_df.to_dict(orient="records")
    return response_dicts
```

**Key points**:
- `check_for_cache()` returns: True (use cache), False (download), or waits for user input
- Cache file naming: `cache_[label].[suffix]`
- Always save downloaded data to cache
- Convert to list of dicts at end

### 3.2 Metadata and Upload Pattern

```python
def run_everything(folder=""):
    # 1. Retrieve data
    raw_dicts = retrieve_data(folder)
    
    # 2. Load mapping
    custom_mapping = retrieve_mapping(folder)
    
    # 3. Get registry metadata (create if new)
    meta_id, skip = meta_check(registry_name, source_url)
    
    # 4. Prepare static fields
    static_amendment = {
        "registryName": registry_name,
        "registryID": meta_id,
        "legalNotices": [legal_notice]  # Required
    }
    
    # 5. Upload if not skipped
    if skip != 's':
        final_results = send_all_to_mongodb(
            raw_dicts, 
            custom_mapping, 
            static_amendment
        )
    
    # 6. Record completion time
    completion_timestamp(meta_id)
    return final_results
```

### 3.3 Legal Notice Pattern

All registries include legal notices:

```python
legal_notice = {
    "title": "License Name",
    "description": "Full license text...",
    "url": "https://license-url.com"
}

# For New Zealand (special notice):
legal_notice = {
    "function": "No Email Solicitation",
    "title": "Unsolicited Electronic Messages Act 2007",
    "description": "..."
}

static_amendment = {
    "legalNotices": [legal_notice],
    "registryName": registry_name,
    "registryID": meta_id
}
```

### 3.4 Progress Tracking Pattern

**For batch uploads**:
```python
# This is already in send_all_to_mongodb, but pattern is:
for i, record in enumerate(records, start=1):
    if (i % 100 == 0) or (i == len(records)):
        percentage = "%.2f" % (100 * i / len(records))
        print(f"\r {i}/{len(records)} ({percentage}%) records processed", end="")
```

**For filing matching**:
```python
reference_time = datetime.now()
reference_unmatched = n_unmatched

while n_unmatched > 0:
    # Do work
    n_unmatched -= 1
    
    # Check if 5 minutes passed
    time_difference = datetime.now() - reference_time
    if time_difference.total_seconds() > (5 * 60):
        unmatched_difference = reference_unmatched - n_unmatched
        print(f"5 minutes: {unmatched_difference} matches completed")
        reference_time = datetime.now()
        reference_unmatched = n_unmatched
```

### 3.5 Error Handling Patterns

**Menu input validation** (in interface.py):
```python
selection = input("Choose option: ")
while True:
    if selection in valid_options:
        break
    else:
        print("Invalid option")
        selection = input("Try again: ")
```

**Data quality checks** (in retrieve.py):
```python
if response.status_code != 200:
    raise Exception(f"Status Code {response.status_code} is not 200")
```

**Graceful interruption** (in match_filing loop):
```python
try:
    while n_unmatched > 0:
        filing = mongo_regeindary[filings].find_one(unmatched_identifier)
        match_filing(filing)
        n_unmatched -= 1
except KeyboardInterrupt:
    print("Matching Process Stopped")
```

## 4. SCHEMA FIELD CONVENTIONS

### 4.1 When to Use Which Field

| Field | When to Use | Example |
|-------|------------|---------|
| entityId | Public registry number | ABN, Charity Number, EIN |
| entityIndex | Internal system number | Organisation Number (UK) |
| subsidiaryId | Nested organization | Linked charity number (UK) |
| entityName | Official name | "National Cancer Society" |
| registeredDate | When registered in system | First appeared in registry |
| establishedDate | When actually founded | When organization was created |
| websiteUrl | Official website | From registry listing |
| recordId | Specific year/filing record | Different per year |
| recordIndex | Internal index for records | If registry uses one |

### 4.2 Mapping Field Names to Schema

**Australia example**:
```json
[
  {"origin": "Charity_Legal_Name", "target": "entityName"},
  {"origin": "Charity_Website", "target": "websiteUrl"},
  {"origin": "ABN", "target": "entityId"},
  {"origin": "Date_Organisation_Established", "target": "establishedDate"}
]
```

**EnglandWales example**:
```json
[
  {"origin": "charity_name", "target": "entityName"},
  {"origin": "registered_charity_number", "target": "entityId"},
  {"origin": "organisation_number", "target": "entityIndex"},
  {"origin": "linked_charity_number", "target": "subsidiaryIndex"}
]
```

**Rule**: If source field has no natural mapping, don't force it. Leave it for future enhancement via "Keyword Match Assist".

## 5. COMMON IMPLEMENTATION PATTERNS

### 5.1 CSV-Based Registry (Australia, NewZealand)

```python
def retrieve_data(folder):
    cached = check_for_cache(folder)
    
    if cached:
        response_df = pd.read_csv(f"{folder}cache.csv", 
                                 encoding_errors="backslashreplace")  # Special for AU
    elif cached is False:
        response_df = pd.read_csv(api_url, headers=headers)
        response_df.to_csv(f"{folder}cache.csv")
    else:
        raise Exception
    
    response_dicts = response_df.to_dict(orient="records")
    return response_dicts
```

### 5.2 JSON-Based Registry (EnglandWales)

```python
def retrieve_data(folder, label):
    cached = check_for_cache(folder, label=label, suffix="json")
    
    if cached:
        pass  # Just load below
    elif cached is False:
        retrieval_with_unzip(label)  # Download and extract
    
    with open(f"{folder}cache_{label}.json", encoding="utf-8-sig") as js:
        response_dicts = json.load(js)
    
    return response_dicts
```

### 5.3 Multi-File Registry (UnitedStates)

```python
def retrieve_entities():
    # Download 4 regional files
    eo_master = None
    for i in range(1, 5):
        df = pd.read_csv(url.format(i=i))
        if eo_master is None:
            eo_master = df
        else:
            eo_master = pd.concat([eo_master, df], ignore_index=True)
    
    eo_master.to_csv("cache_entities.csv", index=False)
    eo_dicts = eo_master.to_dict(orient="records")
    return eo_dicts
```

## 6. INTERFACE.PY EXTENSION PATTERN

To add a new registry to the menu:

```python
# Step 1: Update retrieval_options string
retrieval_options = """[1] Australia
[2] England and Wales
[3] New Zealand
[4] United States
[5] New Registry Name      <-- ADD HERE
[A] Run All
[X] Exit"""

# Step 2: Update all_options range
all_options = [str(x) for x in range(1, 6)]  # Change from 5 to 6

# Step 3: Add elif branch
elif s == "5":
    import scripts.NewRegistry.retrieve as newreg
    newreg.run_everything("NewRegistry/")
```

## 7. TESTING PATTERNS

### 7.1 Pre-Import Testing

```python
# Test 1: Can retrieve raw data?
from scripts.NewCountry.retrieve import retrieve_data
raw = retrieve_data("NewCountry/")
assert len(raw) > 0, "No data retrieved"
print(raw[0])  # Inspect first record

# Test 2: Does mapping work?
from scripts.utils import retrieve_mapping
mapping = retrieve_mapping("NewCountry/")
assert len(mapping) > 0, "No mappings loaded"

# Test 3: Can connect to MongoDB?
from scripts.utils import mongo_regeindary
assert mongo_regeindary is not None, "MongoDB connection failed"

# Test 4: Import small batch
from scripts.utils import send_all_to_mongodb, meta_check
meta_id, _ = meta_check("Test Registry", "http://test.com")
results = send_all_to_mongodb(raw[:5], mapping, 
                              {"registryID": meta_id, 
                               "registryName": "Test Registry"})

# Test 5: Verify in database
from scripts.utils import get_random_entity
entity = get_random_entity(mongo_filter={"registryID": meta_id})
print(entity)
```

### 7.2 Built-in Testing Tools

Users can test your implementation with:
1. **Status Check** - Shows counts and timestamps
2. **Keyword Match Assist** - Shows which schema fields are covered
3. **Random Entity Display** - Shows actual data with mappings applied

## 8. PERFORMANCE CONSIDERATIONS

### 8.1 Indexing

Indexes are automatically created by `run_all_match_filings()`:

```python
# Called automatically:
index_check(organizations, ['registryID', 'entityId'])
index_check(organizations, ['registryID', 'entityIndex'])
index_check(filings, ['registryID', 'entityId'])
```

If you add a new query pattern, add corresponding index.

### 8.2 Batch Processing

Use `batch_size` parameter in `run_all_match_filings()`:
```python
# From interface.py:
if batch_size == "!":
    utils.run_all_match_filings()          # All filings
else:
    utils.run_all_match_filings(int(batch_size))  # N filings
```

### 8.3 Memory Management

For large datasets (like US with 500k+ records):
```python
# Preserve memory with categorical types
categorical_columns = ["EIN", "STATUS", ...]
df = pd.read_csv(url, dtype={col: str for col in categorical_columns})

# Use low_memory=False only when necessary
df = pd.read_csv(url, low_memory=False)  # NewZealand
```

## 9. COMMON PITFALLS TO AVOID

1. **Don't commit local cache files**
   - They're generated at runtime
   - Add to .gitignore

2. **Don't modify Original Data field**
   - Always preserve the raw source record
   - For audit trail

3. **Don't skip the legal notice**
   - Include in every registry
   - Required for compliance

4. **Don't assume ID format**
   - US requires: `.rjust(9, '0')`
   - Some registries may differ

5. **Don't remove completion_timestamp()**
   - Used for status tracking
   - Essential for monitoring

6. **Don't use hardcoded paths**
   - Use relative paths from folder parameter
   - Must work from any directory

7. **Don't forget encoding specification**
   - Australia: `encoding_errors="backslashreplace"`
   - EnglandWales: `encoding="utf-8-sig"`

## 10. CHECKLIST FOR NEW REGISTRY IMPLEMENTATION

- [ ] Created `/scripts/[Country]/` directory
- [ ] Created `retrieve.py` with `retrieve_data()` and `run_everything()`
- [ ] Created `mapping.json` with all discoverable field mappings
- [ ] Added legal notice(s) in `run_everything()`
- [ ] Updated `interface.py` menu and retrieval_registries()
- [ ] Tested data retrieval with `Status Check`
- [ ] Tested field mapping with `Keyword Match Assist`
- [ ] Verified MongoDB documents have all required fields
- [ ] All Original Data preserved
- [ ] Progress tracking working (every 100 records)
- [ ] Cache files generated and user prompted on re-run
- [ ] If including filings, separate collection handling implemented
- [ ] If date formatting needed, documented in mapping.json

