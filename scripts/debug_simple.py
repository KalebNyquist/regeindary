"""Simple debug script to check MongoDB state - no utils.py import needed."""
import pymongo
import tomllib
import os
from datetime import datetime

# Load config
config_path = os.path.join(os.path.dirname(__file__), 'config.toml')
with open(config_path, "rb") as cfg:
    config = tomllib.load(cfg)

# Connect to MongoDB
client = pymongo.MongoClient(config['mongo_path'])
db = client[config['database_name']]
orgs = db[config['organization_collection']]
meta_col = db[config['meta_collection']]

print("=" * 70)
print("MONGODB STATE CHECK (OPTIMIZED)")
print("=" * 70)

# Create indexes for fast queries
print("\n0. Creating indexes for fast queries...")
start = datetime.now()
orgs.create_index([("registryID", pymongo.ASCENDING)])
orgs.create_index([("registryID", pymongo.ASCENDING), ("entityId", pymongo.ASCENDING)])
orgs.create_index([("registryName", pymongo.ASCENDING)])
orgs.create_index([("registryName", pymongo.ASCENDING), ("entityId", pymongo.ASCENDING)])
elapsed = (datetime.now() - start).total_seconds()
print(f"   ✔ Indexes created/verified in {elapsed:.2f}s")

# Get registry metadata
print("\n1. Registry Metadata:")
registry_meta = meta_col.find_one({"name": "Australia - ACNC Charity Register"})
if registry_meta:
    registry_id = registry_meta['_id']
    print(f"   Found: {registry_meta['name']}")
    print(f"   _id: {registry_id}")
    print(f"   Type: {type(registry_id).__name__}")
else:
    print("   ❌ NOT FOUND!")
    exit(1)

# Count existing records (with index hints for speed)
print("\n2. Existing Records Count:")
start = datetime.now()
count_by_id = orgs.count_documents({"registryID": registry_id}, hint="registryID_1")
elapsed = (datetime.now() - start).total_seconds()
print(f"   By registryID: {count_by_id:,} ({elapsed:.2f}s)")

count_by_name = orgs.count_documents({"registryName": "Australia - ACNC Charity Register"})
print(f"   By registryName: {count_by_name:,}")

if count_by_id == 0:
    print("   ❌ NO EXISTING RECORDS FOUND!")
    print("   This is why duplicate detection shows 0 duplicates.")
    exit(0)

# Check entityId field
print("\n3. Field Check:")
with_entityId = orgs.count_documents({"registryID": registry_id, "entityId": {"$exists": True}})
print(f"   Records with 'entityId' field: {with_entityId:,} / {count_by_id:,}")

# Sample records
print("\n4. Sample Record:")
sample = orgs.find_one({"registryID": registry_id})
if sample:
    print(f"   _id: {sample.get('_id')}")
    print(f"   registryID: {sample.get('registryID')} (matches: {sample.get('registryID') == registry_id})")
    print(f"   entityId: {sample.get('entityId')} (exists: {'entityId' in sample})")
    print(f"   entityName: {sample.get('entityName')}")
    print(f"   All keys: {', '.join(sample.keys())}")

    # Check entityId value and type
    if 'entityId' in sample:
        eid = sample['entityId']
        print(f"\n   entityId details:")
        print(f"     Value: {eid}")
        print(f"     Type: {type(eid).__name__}")
        print(f"     As string: '{str(eid)}'")

# Sample 5 entityIds to see pattern
print("\n5. Sample entityId values (first 5):")
samples = orgs.find({"registryID": registry_id, "entityId": {"$exists": True}}, {"entityId": 1, "_id": 0}).limit(5)
for i, doc in enumerate(samples, 1):
    eid = doc.get('entityId')
    print(f"   {i}. {eid}")

print("\n" + "=" * 70)
