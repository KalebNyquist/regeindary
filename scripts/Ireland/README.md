# Ireland - Charities Regulator

## Data Source

**Source URL**: https://data.gov.ie/dataset/register-of-charities-in-ireland
**Registry**: Charities Regulator (Ireland)
**License**: Creative Commons Attribution 4.0 International (CC-BY 4.0)

## Data Files

This module retrieves two datasets:

1. **Entities** (Register of Charities):
   https://www.charitiesregulator.ie/media/d52jwriz/register-of-charities.csv

2. **Filings** (Annual Reports):
   https://www.charitiesregulator.ie/media/yeia3rfc/charity-annual-reports.csv

## Setup Instructions

### Step 1: Verify Field Mappings

The `mapping.json` file contains placeholder field names that need to be verified and updated based on the actual CSV column names.

To check the actual column names:

```python
import pandas as pd

# Check entities columns
df_entities = pd.read_csv('https://www.charitiesregulator.ie/media/d52jwriz/register-of-charities.csv')
print("Entity columns:")
print(df_entities.columns.tolist())

# Check filings columns
df_filings = pd.read_csv('https://www.charitiesregulator.ie/media/yeia3rfc/charity-annual-reports.csv')
print("\nFiling columns:")
print(df_filings.columns.tolist())
```

### Step 2: Update mapping.json

Once you know the actual column names, update `mapping.json` to map the source fields to the standardized schema fields.

**Entity field mappings** (target fields from `schemas/entity.json`):
- `entityName` - Organization name
- `entityId` - Charity registration number
- `registeredDate` - Date registered with regulator
- `websiteUrl` - Organization website
- `establishedDate` - Date organization was established

**Filing field mappings** (target fields from `schemas/filing.json`):
- `entityId` - Charity number (links to entity)
- `startDate` - Financial period start date
- `endDate` - Financial period end date
- `recordDate` - Date the filing was received
- `totalIncome` - Total income for the period
- `totalExpenditures` - Total expenditures for the period

### Step 3: Date Format Handling

If the CSV uses a date format other than YYYY-MM-DD, add a `"format"` key to the mapping:

```json
{
  "origin": "Registration Date",
  "target": "registeredDate",
  "format": "DD/MM/YYYY"
}
```

Common formats:
- `DD/MM/YYYY` - e.g., 25/12/2020
- `MM/DD/YYYY` - e.g., 12/25/2020
- `YYYY-MM-DD` - e.g., 2020-12-25 (ISO format, no format key needed)

## Running the Import

Once the mapping is verified:

```bash
cd /home/user/regeindary/scripts
python interface.py
```

Select option `[2] Retrieve Registries`, then choose `[3] Ireland`.

## Troubleshooting

### Download Errors (403 Forbidden / Cloudflare Protection)

**Known Issue**: The Charities Regulator website uses Cloudflare protection which may block automated downloads with a 403 error.

The `retrieve.py` script attempts two download methods:
1. **pandas.read_csv** - Sometimes bypasses Cloudflare
2. **requests with enhanced headers** - Mimics browser behavior

If both fail, you'll see instructions for manual download. To manually download:

1. **Download the CSV files** from your browser:
   - **Entities**: https://www.charitiesregulator.ie/media/d52jwriz/register-of-charities.csv
   - **Filings**: https://www.charitiesregulator.ie/media/yeia3rfc/charity-annual-reports.csv

2. **Save them** in `/home/user/regeindary/scripts/Ireland/` as:
   - `cache_entities.csv` (for the register of charities)
   - `cache_filings.csv` (for the annual reports)

3. **Re-run the import** - The script will detect and use the cached files

**Alternative**: You can also use `curl` or `wget` from the command line if you have cookies from a browser session

### Field Mapping Issues

After import, use the built-in tools to verify data quality:

```
[1] Run Status Check - See how many records were imported
[3] Keyword Match Assist - Check which fields are mapped
[5] Display Random Entity - Inspect actual data
```

### Missing Fields

Not all fields need to be mapped. Unmapped fields are preserved in the "Original Data" section of each MongoDB document.

## Notes

- **Update Frequency**: The register is updated weekly according to data.gov.ie
- **Data Coverage**: Includes all registered charities in Ireland
- **Filings**: Annual reports filed with the Charities Regulator

## References

- [Charities Regulator Website](https://www.charitiesregulator.ie/en)
- [Data Portal](https://data.gov.ie/dataset/register-of-charities-in-ireland)
- [CC-BY 4.0 License](https://creativecommons.org/licenses/by/4.0/)
