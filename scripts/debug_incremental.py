"""Debug script to diagnose incremental update duplicate detection issues."""
from utils import *

print("=" * 70)
print("INCREMENTAL UPDATE DEBUGGING")
print("=" * 70)

# Check registry metadata
print("\n1. Checking Registry Metadata:")
print("-" * 70)
registry_meta = mongo_regeindary[meta].find_one({"name": "Australia - ACNC Charity Register"})
if registry_meta:
    print(f"  Registry _id: {registry_meta['_id']}")
    print(f"  Registry _id type: {type(registry_meta['_id']).__name__}")
    print(f"  Registry name: {registry_meta['name']}")
    registry_id = registry_meta['_id']
else:
    print("  ❌ No registry metadata found!")
    exit(1)

# Check existing records
print("\n2. Checking Existing Records:")
print("-" * 70)
count_by_name = mongo_regeindary[orgs].count_documents({"registryName": "Australia - ACNC Charity Register"})
count_by_id = mongo_regeindary[orgs].count_documents({"registryID": registry_id})
print(f"  Records with registryName='Australia - ACNC Charity Register': {count_by_name:,}")
print(f"  Records with registryID={registry_id}: {count_by_id:,}")

if count_by_name != count_by_id:
    print(f"  ⚠️  Mismatch! Some records may have different registryID values")

# Sample a few records
print("\n3. Sample Records:")
print("-" * 70)
sample_records = mongo_regeindary[orgs].find({"registryID": registry_id}).limit(3)

for i, record in enumerate(sample_records, 1):
    print(f"\n  Record {i}:")
    print(f"    _id: {record.get('_id')}")
    print(f"    registryID: {record.get('registryID')}")
    print(f"    registryID matches: {record.get('registryID') == registry_id}")
    print(f"    entityId exists: {'entityId' in record}")
    print(f"    entityId value: {record.get('entityId')}")
    print(f"    entityId type: {type(record.get('entityId')).__name__}")
    print(f"    entityName: {record.get('entityName')}")
    print(f"    All top-level keys: {', '.join(record.keys())}")

# Check if entityId field exists in all records
print("\n4. Checking entityId Field Coverage:")
print("-" * 70)
total_count = mongo_regeindary[orgs].count_documents({"registryID": registry_id})
with_entityId = mongo_regeindary[orgs].count_documents({"registryID": registry_id, "entityId": {"$exists": True}})
print(f"  Total Australia records: {total_count:,}")
print(f"  Records with 'entityId' field: {with_entityId:,}")
print(f"  Coverage: {100 * with_entityId / total_count if total_count > 0 else 0:.1f}%")

if with_entityId < total_count:
    print(f"  ⚠️  {total_count - with_entityId:,} records missing 'entityId' field!")

# Sample some entityId values
print("\n5. Sample entityId Values:")
print("-" * 70)
sample_ids = mongo_regeindary[orgs].find(
    {"registryID": registry_id, "entityId": {"$exists": True}},
    {"entityId": 1, "_id": 0}
).limit(10)

for i, doc in enumerate(sample_ids, 1):
    entity_id = doc.get('entityId')
    print(f"  {i}. {entity_id} (type: {type(entity_id).__name__}, str: '{str(entity_id)}')")

print("\n" + "=" * 70)
print("Debug complete!")
print("=" * 70)
