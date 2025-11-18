"""Core utility functions for Regeindary registry data aggregation.

This module provides MongoDB operations, field mapping, data upload, and entity-filing
matching functionality for importing heterogeneous civil society registry data into
a unified database structure.
"""
import inspect
import tomllib
import os

import bson
import pymongo
import json
from datetime import datetime
from pprint import pp
import random
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# Add the project root directory to sys.path if it's not already there
project_root = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_root)
if parent_dir not in sys.path:
    logger.debug(f"Adding project root to sys.path: {parent_dir}")
    sys.path.append(parent_dir)


# Prerequisite Functions to Create Globals
def get_config():
    """Load MongoDB configuration from config.toml file.

    Returns:
        dict: Configuration dictionary containing MongoDB connection settings.

    Raises:
        FileNotFoundError: If config.toml is not found in the scripts directory.
        ValueError: If the TOML file contains invalid syntax.
    """

    # Get the absolute path to the config file
    config_path = os.path.join(os.path.dirname(__file__), 'config.toml')
    config_path = os.path.abspath(config_path)

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Configuration file not found at: {config_path}\n"
            f"Please create a config.toml file with MongoDB connection settings.\n"
            f"See README.md for configuration instructions."
        )

    try:
        with open(config_path, "rb") as cfg:
            config = tomllib.load(cfg)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(
            f"Invalid TOML syntax in config file: {config_path}\n"
            f"Error: {e}"
        )

    return config


def get_mongo_dbs():
    """Initialize MongoDB client and return database and collection mappings.

    Returns:
        tuple: A tuple containing:
            - mongodb_regeindary (Database): MongoDB database instance
            - collections (dict): Dictionary mapping collection names to their configured names
    """
    config = get_config()

    py_client = pymongo.MongoClient(config['mongo_path'])
    mongodb_regeindary = py_client[config['database_name']]

    collections = {
        "organizations": config['organization_collection'],
        "filings": config['filings_collection'],
        "registries": config['meta_collection']
    }

    return mongodb_regeindary, collections


# Globals
mongo_regeindary, collections_map = get_mongo_dbs()
meta = collections_map['registries']
orgs = collections_map['organizations']
filings = collections_map['filings']


def check_for_cache(folder="", label="", suffix="csv"):
    """Check if a cached data file exists and prompt user whether to use it.

    Args:
        folder (str): Directory path where cache file is located. Defaults to "".
        label (str): Label to distinguish cache files. Defaults to "".
        suffix (str): File extension for cache file. Defaults to "csv".

    Returns:
        bool: True if cached file should be used, False if new download is needed.
    """

    if label == "":
        underscore_value = ""
    else:
        underscore_value = "_"

    cache_path = f'{folder}cache{underscore_value}{label}.{suffix}'
    logger.info(f"Checking cache path: {cache_path}")
    if os.path.exists(cache_path):
        logger.info("Cached file found")
        cached = None
        while cached is None:
            option = input(" Download new copy? (y/n) ")
            if option.lower() == "y":
                cached = False
            elif option.lower() == "n":
                cached = True
            else:
                print(" Invalid option. Select 'y' or 'n'.")
        logger.info(f"Using cached file: {cached}")
    else:
        logger.info("No cached file found, will download fresh data")
        cached = False
    return cached


def delete_old_records(registry_id, collection='organizations'):
    """Check for existing records and prompt user to delete them or use incremental update.

    Args:
        registry_id (ObjectId): MongoDB ObjectId of the registry.
        collection (str): Collection name ('organizations' or 'filings'). Defaults to 'organizations'.

    Returns:
        str or int: 'y' if records deleted, 'n' if skipped, 's' to skip upload,
                    'i' for incremental update, or 0 if no records exist.
    """
    global mongo_regeindary, collections_map

    record_count = mongo_regeindary[collections_map[collection]].count_documents({"registryID": registry_id})
    logger.info(f"Found {record_count:,} existing records for this registry in '{collection}' collection")
    if record_count > 0:
        delete_option = None
        option = None
        while delete_option is None:
            print(f" Found {record_count:,} existing records. Choose an option:")
            print("   [y] Delete all old records and insert new data")
            print("   [i] Incremental update (insert only new records)")
            print("   [n] Keep old records (may cause duplicate errors)")
            print("   [s] Skip upload entirely")
            option = input(" Your choice: ").lower().strip()
            if option == "y":
                delete_option = True
            elif option in ["n", "s", "i"]:
                delete_option = False
            else:
                print(" Invalid option. Select 'y', 'i', 'n', or 's'.")
        if delete_option:
            logger.warning(f"Deleting {record_count:,} existing records from '{collection}' collection")
            mongo_regeindary[collections_map[collection]].delete_many({"registryID": registry_id})
            logger.info("Old records deleted successfully")
            option = "y"
        return option
    return record_count


def send_all_to_mongodb(records, mapping, static, collection='organizations'):
    """Upload multiple records to MongoDB using batch insertion with progress tracking.

    Optimized to use insert_many() for batch insertion instead of looping insert_one().
    Pre-processes all records to apply mapping transformations, then inserts all documents
    in a single batch operation for better performance.

    Args:
        records (list): List of record dictionaries to upload.
        mapping (dict): Field mapping dictionary (origin field -> target field).
        static (dict): Static fields to add to every record (e.g., registryID, registryName).
        collection (str): Target collection name. Defaults to 'organizations'.

    Returns:
        dict: Dictionary mapping record index (1-based) to MongoDB ObjectIds.
    """
    global mongo_regeindary, collections_map

    # Pre-process all records to apply mapping transformations
    upload_documents = []
    logger.info(f"Transforming {len(records):,} records for MongoDB insertion")
    for i, record in enumerate(records, start=1):
        if (i % 100 == 0) or (i == len(records)):
            percentage = "%.2f" % (100 * i/len(records))
            print(f"\r  Transformed {i:,}/{len(records):,} ({percentage}%) records", end="")

        # Apply mapping transformation (same logic as send_to_mongodb)
        upload_dict = static.copy()
        for m in mapping.keys():
            if m in record.keys():
                upload_dict.update({mapping[m]: record[m]})
        upload_dict.update({"Original Data": record})
        upload_documents.append(upload_dict)

    print()  # New line after transformation progress

    # Batch insert all documents at once
    logger.info(f"Inserting {len(upload_documents):,} documents to '{collection}' collection")
    result = mongo_regeindary[collections_map[collection]].insert_many(
        upload_documents,
        ordered=False  # Continue on error, more resilient for large batches
    )
    logger.info(f"✔ Successfully inserted {len(result.inserted_ids):,} documents")

    # Return results in compatible format
    results = {i+1: result.inserted_ids[i] for i in range(len(result.inserted_ids))}
    return results


def send_to_mongodb(record, mapping, static, collection):
    """Upload a single record to MongoDB with field mapping applied.

    Args:
        record (dict): Record dictionary to upload.
        mapping (dict): Field mapping dictionary (origin field -> target field).
        static (dict): Static fields to add to the record.
        collection (str): Target collection name.

    Returns:
        InsertOneResult: MongoDB insert result object.
    """
    global mongo_regeindary, collections_map
    upload_dict = static.copy()
    for m in mapping.keys():
        if m in record.keys():
            upload_dict.update({mapping[m]: record[m]})

    upload_dict.update({"Original Data": record})
    result = mongo_regeindary[collections_map[collection]].insert_one(upload_dict)

    return result


def preview_new_records(records, mapping, static, collection='organizations', unique_field='entityId'):
    """Analyze incoming records to identify new vs existing records before insertion.

    Compares incoming records with existing MongoDB records to determine which are new.
    For organizations, typically use unique_field='entityId'.
    For filings, typically use unique_field='filingId' or 'filingIndex'.

    Args:
        records (list): List of record dictionaries to analyze.
        mapping (dict): Field mapping dictionary (origin field -> target field).
        static (dict): Static fields (must include registryID).
        collection (str): Target collection name. Defaults to 'organizations'.
        unique_field (str): Field name to use for uniqueness detection. Defaults to 'entityId'.

    Returns:
        tuple: (new_records, duplicate_records, new_indices, duplicate_indices)
            - new_records (list): Records that don't exist in MongoDB
            - duplicate_records (list): Records that already exist in MongoDB
            - new_indices (list): Indices of new records in original list
            - duplicate_indices (list): Indices of duplicate records in original list
    """
    global mongo_regeindary, collections_map

    registry_id = static.get('registryID')
    if not registry_id:
        raise ValueError("static dict must contain 'registryID' for duplicate detection")

    logger.info(f"Analyzing {len(records):,} records for duplicates in '{collection}' collection")
    print(f"\nAnalyzing new data...")
    print(f"  ✔ Found {len(records):,} records in source data")

    # Get all existing unique field values for this registry
    existing_count = mongo_regeindary[collections_map[collection]].count_documents({"registryID": registry_id})
    print(f"  ✔ Found {existing_count:,} existing records in MongoDB for this registry")

    # Build set of existing IDs for fast lookup
    print(f"  Fetching existing {unique_field} values...", end="")
    existing_ids = set()
    cursor = mongo_regeindary[collections_map[collection]].find(
        {"registryID": registry_id},
        {unique_field: 1, "_id": 0}
    )
    for doc in cursor:
        if unique_field in doc:
            existing_ids.add(str(doc[unique_field]))
    print(" ✔")

    # Categorize incoming records
    print(f"  Categorizing records...", end="")
    new_records = []
    duplicate_records = []
    new_indices = []
    duplicate_indices = []

    # Find the origin field that maps to the unique field
    origin_field = None
    for origin, target in mapping.items():
        if target == unique_field:
            origin_field = origin
            break

    if not origin_field:
        # unique_field might be in static fields or not mapped
        logger.warning(f"Could not find mapping for unique_field '{unique_field}' - trying direct field access")
        origin_field = unique_field

    for i, record in enumerate(records):
        record_id = str(record.get(origin_field, ""))
        if record_id and record_id in existing_ids:
            duplicate_records.append(record)
            duplicate_indices.append(i)
        else:
            new_records.append(record)
            new_indices.append(i)

    print(" ✔")

    # Display results
    print("\n" + "="*70)
    print("PREVIEW RESULTS".center(70))
    print("="*70)
    print(f"  • {len(new_records):,} new records (not in database)")
    print(f"  • {len(duplicate_records):,} duplicate records (already exist)")
    print("="*70 + "\n")

    logger.info(f"Preview complete: {len(new_records):,} new, {len(duplicate_records):,} duplicates")

    return new_records, duplicate_records, new_indices, duplicate_indices


def send_new_to_mongodb(records, mapping, static, collection='organizations', unique_field='entityId'):
    """Upload only new records to MongoDB, skipping duplicates.

    First previews records to identify new vs existing, then prompts user for action.
    Only inserts records that don't already exist in the database.

    Args:
        records (list): List of record dictionaries to upload.
        mapping (dict): Field mapping dictionary (origin field -> target field).
        static (dict): Static fields to add to every record (must include registryID).
        collection (str): Target collection name. Defaults to 'organizations'.
        unique_field (str): Field name to use for uniqueness detection. Defaults to 'entityId'.

    Returns:
        dict: Dictionary mapping record index (1-based) to MongoDB ObjectIds for inserted records.
    """
    global mongo_regeindary, collections_map

    # Preview records
    new_records, duplicate_records, new_indices, duplicate_indices = preview_new_records(
        records, mapping, static, collection, unique_field
    )

    if len(new_records) == 0:
        print("✔ No new records to insert (all records already exist)")
        logger.info("No new records to insert")
        return {}

    # Prompt user for action
    print("What would you like to do?")
    print("  [1] Insert only new records (skip duplicates)")
    print("  [2] Show sample of new records")
    print("  [3] Cancel operation")

    while True:
        choice = input("\nSelect option (1-3): ").strip()

        if choice == "1":
            # Insert new records only
            logger.info(f"User selected: Insert {len(new_records):,} new records")
            return send_all_to_mongodb(new_records, mapping, static, collection)

        elif choice == "2":
            # Show sample in MongoDB format (after mapping applied)
            sample_size = min(5, len(new_records))
            print(f"\nShowing {sample_size} sample new records (as they'll appear in MongoDB):")
            print("-" * 70)
            for i in range(sample_size):
                # Apply mapping transformation to show how it will look in MongoDB
                upload_dict = static.copy()
                for m in mapping.keys():
                    if m in new_records[i].keys():
                        upload_dict.update({mapping[m]: new_records[i][m]})
                upload_dict.update({"Original Data": new_records[i]})

                print(f"\nRecord {i+1}:")
                pp(upload_dict)
            print("-" * 70)
            # Loop back to menu
            print("\nWhat would you like to do?")
            print("  [1] Insert only new records (skip duplicates)")
            print("  [2] Show sample of new records")
            print("  [3] Cancel operation")

        elif choice == "3":
            logger.info("User cancelled operation")
            print("✔ Operation cancelled")
            return {}

        else:
            print("Invalid option. Please select 1, 2, or 3.")


def upsert_all_to_mongodb(records, mapping, static, collection='organizations', unique_field='entityId'):
    """Update existing records and insert new ones (upsert operation).

    For each record, updates it if it exists (based on registryID + unique_field),
    or inserts it if it doesn't exist.

    Args:
        records (list): List of record dictionaries to upsert.
        mapping (dict): Field mapping dictionary (origin field -> target field).
        static (dict): Static fields to add to every record (must include registryID).
        collection (str): Target collection name. Defaults to 'organizations'.
        unique_field (str): Field name to use for matching. Defaults to 'entityId'.

    Returns:
        dict: Dictionary with counts of modified, inserted, and total operations.
    """
    global mongo_regeindary, collections_map

    registry_id = static.get('registryID')
    if not registry_id:
        raise ValueError("static dict must contain 'registryID' for upsert operation")

    # Find the origin field that maps to the unique field
    origin_field = None
    for origin, target in mapping.items():
        if target == unique_field:
            origin_field = origin
            break

    if not origin_field:
        logger.warning(f"Could not find mapping for unique_field '{unique_field}' - trying direct field access")
        origin_field = unique_field

    logger.info(f"Upserting {len(records):,} records to '{collection}' collection")
    print(f"\nUpserting {len(records):,} records...")

    modified_count = 0
    inserted_count = 0

    for i, record in enumerate(records, start=1):
        if (i % 100 == 0) or (i == len(records)):
            percentage = "%.2f" % (100 * i/len(records))
            print(f"\r  Processed {i:,}/{len(records):,} ({percentage}%) records", end="")

        # Apply mapping transformation
        upload_dict = static.copy()
        for m in mapping.keys():
            if m in record.keys():
                upload_dict.update({mapping[m]: record[m]})
        upload_dict.update({"Original Data": record})

        # Get unique identifier value
        unique_value = str(record.get(origin_field, ""))

        # Upsert operation
        result = mongo_regeindary[collections_map[collection]].update_one(
            {"registryID": registry_id, unique_field: unique_value},
            {"$set": upload_dict},
            upsert=True
        )

        if result.matched_count > 0:
            modified_count += 1
        elif result.upserted_id:
            inserted_count += 1

    print()  # New line after progress
    logger.info(f"✔ Upsert complete: {inserted_count:,} inserted, {modified_count:,} updated")
    print(f"✔ Upsert complete: {inserted_count:,} new records inserted, {modified_count:,} existing records updated")

    return {
        "inserted": inserted_count,
        "modified": modified_count,
        "total": len(records)
    }


def meta_check(registry_name, source_url, collection="organizations"):
    """Check if registry exists in metadata collection, create if needed, and manage old records.

    Args:
        registry_name (str): Name of the registry (e.g., "Australia - ACNC Charity Register").
        source_url (str): URL of the registry data source.
        collection (str): Collection to check for old records. Defaults to "organizations".

    Returns:
        tuple: A tuple containing:
            - registry_id (ObjectId): MongoDB ObjectId of the registry metadata
            - decision (str or None): User's deletion decision ('y', 'n', 's', or None)

    Raises:
        Exception: If multiple registries with the same name exist (database integrity error).
    """
    preexisting_registries = mongo_regeindary[meta].count_documents({"name": registry_name})

    if preexisting_registries == 0:
        logger.info(f"Registry '{registry_name}' not found in metadata collection - creating new entry")
        result = mongo_regeindary[meta].insert_one({
            "name": registry_name,
            "source": source_url
        })
        logger.info(f"Created new registry metadata with ID: {result.inserted_id}")
        return result.inserted_id, None
    elif preexisting_registries == 1:
        logger.info(f"Registry '{registry_name}' found in metadata collection")
        result = mongo_regeindary[meta].find_one({"name": registry_name})
        decision = delete_old_records(result['_id'], collection)
        return result['_id'], decision
    elif preexisting_registries >= 2:
        logger.error(f"Database integrity error: Found {preexisting_registries} registries with name '{registry_name}'")
        raise Exception(f"Database integrity error: Found {preexisting_registries} registries with name '{registry_name}'. Expected 0 or 1.")
    else:
        logger.error(f"Unexpected database state: Registry count for '{registry_name}' is {preexisting_registries}")
        raise Exception(f"Unexpected database state: Registry count for '{registry_name}' is {preexisting_registries}. This should not be possible.")


def retrieve_mapping(folder="", level=None):
    """Load field mapping from mapping.json file.

    Args:
        folder (str): Directory containing mapping.json. Defaults to current directory.

    Returns:
        dict: Dictionary mapping origin field names to target field names.
    """
    with open(f"{folder}mapping.json", "r") as m:
        mp = json.load(m)
    if not level:
        mapping = {feature['origin']: feature['target'] for feature in mp}
    if level:
        mapping = {feature['origin']: feature['target'] for feature in mp if level in feature.get('level', ['entities', 'filings'])}
    return mapping


def list_registries():
    """Retrieve all registries from the metadata collection.

    Returns:
        list: List of registry metadata documents.
    """
    mongo_registries = mongo_regeindary[meta].find({})
    mongo_registries = [mongo_registry for mongo_registry in mongo_registries]
    return mongo_registries


def status_check():
    """Display comprehensive database statistics including registries, organizations, and filings.

    Prints:
        - Total counts of registries, organizations, and filings
        - Per-registry statistics with completion timestamps
        - Database size in bytes and gigabytes
    """
    global mongo_regeindary, collections_map

    logger.info("Starting database status check")
    print("  Counting # Registries...", end="")
    n_registries = mongo_regeindary[meta].count_documents({}, hint="_id_")
    print(" ✔\n  Counting # Organizations...", end="")
    n_organizations = mongo_regeindary[orgs].count_documents({}, hint="_id_")
    print(" ✔\n  Counting # Filings...", end="")
    n_filings = mongo_regeindary[filings].count_documents({},  hint="_id_")
    print(" ✔")

    registries = list_registries()

    logger.info(f"Database contains: {n_registries} registries, {n_organizations:,} organizations, {n_filings:,} filings")
    print(f"{n_registries} registries, {n_organizations:,} organizations, and {n_filings:,} filings")
    # Optimized: Use aggregation pipeline to get counts for all registries in 2 queries instead of 2*N queries
    print("  Aggregating counts by registry...", end="")
    org_counts_cursor = mongo_regeindary[orgs].aggregate([
        {"$group": {"_id": "$registryID", "count": {"$sum": 1}}}
    ])
    org_counts = {doc['_id']: doc['count'] for doc in org_counts_cursor}

    filing_counts_cursor = mongo_regeindary[filings].aggregate([
        {"$group": {"_id": "$registryID", "count": {"$sum": 1}}}
    ])
    filing_counts = {doc['_id']: doc['count'] for doc in filing_counts_cursor}
    print(" ✔")

    print(n_registries, "registries,", n_organizations, "organizations, and", n_filings, "filings")
    for registry in registries:
        print(registry['name'].ljust(80, "."), end="")

        completion_time = registry.get("download_completion", False)
        if type(completion_time) is not bool:
            completion_time = datetime.strftime(completion_time, "%b %m %Y %H:%M")
        else:
            completion_time = "NOT COMPLETED YET"
        print(completion_time, end="...................")

        n_orgs_in_registry = mongo_regeindary[orgs].count_documents({'registryID': registry['_id']})
        if n_organizations > 0:
            fraction = n_orgs_in_registry / n_organizations
            percentage = round(fraction * 100, 2)
            percentage = f"{percentage}%"
        else:
            percentage = "N/A"
            
        # Use pre-computed counts from aggregation instead of individual queries
        n_orgs_in_registry = org_counts.get(registry['_id'], 0)
        fraction = n_orgs_in_registry / n_organizations if n_organizations > 0 else 0
        percentage = round(fraction * 100, 2)
        percentage = f"{percentage}%"
        print(f"{n_orgs_in_registry} orgs ({percentage})".ljust(10), end="")
        n_filings_in_registry = filing_counts.get(registry['_id'], 0)
        print(f" & {n_filings_in_registry} filings".ljust(30))

    total_size = mongo_regeindary.command("dbstats")['totalSize']
    size_gb = round((total_size / 1024 ** 3), 2)
    logger.info(f"Total database size: {size_gb} GB ({int(total_size):,} bytes)")
    print(f"{int(total_size):,} bytes = {size_gb} gigabytes")


def keyword_match_assist(select=None):
    """Interactive tool to check field mapping coverage against schema for a selected registry.

    Args:
        select (str, optional): Pre-selected registry option number. If None, prompts user to select.

    Displays:
        - Schema fields that are mapped (✅)
        - Schema fields that are missing (unmapped)
        - Random entity with field-by-field mapping status
    """

    directory_map = {
        "New Zealand - The Charities Register/Te Rēhita Kaupapa Atawhai": "NewZealand",
        "Australia - ACNC Charity Register": "Australia",
        "England and Wales - Charity Commission Register of Charities": "EnglandWales",
        "United States - Internal Revenue Service - Exempt Organizations Business Master File Extract": "UnitedStates"
    }

    mongo_registries = mongo_regeindary[meta].find({})
    options = {}
    for i, mongo_registry in enumerate(mongo_registries, start=1):
        options.update({
            str(i):
                {
                    "name": mongo_registry['name'],
                    "id": mongo_registry['_id']
                }
        }
        )

    if select is None:
        for idx, info in options.items():
            print(f"{idx}: {info['name']}")
        while True:
            select = input("Select registry to check matches: ")
            if select in options.keys():
                break
    else:
        logger.info(f"Registry preselected: {options[select]['name']}")

    # MAIN FUNCTION
    directory = directory_map[options[select]["name"]]

    with open(f"{directory}/mapping.json", "r") as m:
        mapping = json.load(m)
    with open("../schemas/entity.json", "r") as s:
        schema = json.load(s)

    overlap = set.intersection(set([x['target'] for x in mapping]), set(schema['properties'].keys()))
    logger.info(f"Mapped schema fields ({len(overlap)}): {', '.join(sorted(overlap))}")
    print("✅ Schema fields already accounted for:", ", ".join(sorted(overlap)))
    missing = set.difference(set(schema['properties'].keys()), set([x['target'] for x in mapping]))
    logger.info(f"Unmapped schema fields ({len(missing)}): {', '.join(sorted(missing))}")
    print("⬜ Schema fields not accounted for:", ", ".join(sorted(missing)))

    random_entity = get_random_entity(mongo_filter={"registryID": options[select]['id']})

    origin_to_target = {x['origin']: x['target'] for x in mapping}

    longest_key_length = max(len(x) for x in random_entity['Original Data'].keys())
    for x, y in random_entity['Original Data'].items():

        print(x.ljust(longest_key_length + 2), end="")

        if origin_to_target.get(x) in overlap:
            print("✅".ljust(10), end="")
        else:
            print("⬜".ljust(10), end="")

        print(y)


def index_check(collection, identifiers):
    """Create a compound index on specified fields if it doesn't exist.

    Args:
        collection (Collection): MongoDB collection object.
        identifiers (list): List of field names to include in compound index.

    Returns:
        str: Name of the created or existing index.
    """
    desired_index = [(k, pymongo.ASCENDING) for k in identifiers]
    result = collection.create_index(desired_index)
    return result


def create_organization_from_orphan_filing(filing):
    """Create an organization record from a filing that has no matching organization.

    Clones relevant fields from the filing to create a minimal organization record.
    Includes breadcrumb metadata for tracing the auto-generated organization back to its source.

    Args:
        filing (dict): Filing document that has no matching organization.

    Returns:
        ObjectId: MongoDB ObjectId of the newly created organization.
    """

    fields_to_clone = [
        'registryName',
        'registryId',
        'entityId',
        'entityName',
        'establishedDate',
        'websiteUrl'  # this is questionable, given how US Filings have Websites but Orgs do not
    ]

    org_dict = {k: v for k, v in filing.items() if k in fields_to_clone}

    # Generate Function Breadcrumb
    file_name = inspect.getfile(inspect.currentframe())
    function_name = inspect.currentframe().f_code.co_name
    breadcrumb = f"{file_name} {function_name}()"

    original_data = {
        "Generating Function": breadcrumb,
        "Source Filing": filing['_id']
    }

    org_dict.update({"Original Data": original_data})
    result = mongo_regeindary['organizations'].insert_one(org_dict)
    return result.inserted_id


def match_filing(filing, matching_field='entityId', auto_create_from_orphan=True):
    """Link a filing to its corresponding organization by updating the filing's entityId_mongo field.

    Args:
        filing (dict): Filing document to match.
        matching_field (str): Field name to use for matching. Defaults to 'entityId'.
                             Note: Use 'entityIndex' for England/Wales for better matching.
        auto_create_from_orphan (bool): If True, automatically create organization from orphan filing.
                                        If False, prompt user for decision. Defaults to True.

    Returns:
        UpdateResult: MongoDB update result object.

    Raises:
        Exception: If multiple organizations match (database integrity error) or if user declines
                  to create organization from orphan filing.
    """
    # - [ ] note UK/Wales works better when matching_field='entityIndex'
    entity_id = filing[matching_field]
    registry_id = filing['registryID']  # - [ ] registryID -> registryId

    # org_identifier = {"registryID": registry_id, matching_field: entity_id}
    # the below line of code fixes an import error with USA Data, the above line of code is ideal if import error fixed
    org_identifier = {"registryID": registry_id, matching_field: str(entity_id).rjust(9, '0')}

    matched_orgs = mongo_regeindary[orgs].find(org_identifier)
    matched_orgs = [matched_org for matched_org in matched_orgs]

    if len(matched_orgs) == 0:
        if auto_create_from_orphan:
            logger.warning(f"No matching organization found for filing with {matching_field}='{entity_id}' - creating orphan organization")
            entity_id_mongo = create_organization_from_orphan_filing(filing)
        else:
            logger.warning(f"No matching organization found for filing with {matching_field}='{entity_id}'")
            print("⚠️  No matching organization found for filing (see below).")
            pp(filing)
            manual_decision = input("Create Organization from Orphan Filing? (y/n) ")
            if manual_decision == "y":
                entity_id_mongo = create_organization_from_orphan_filing(filing)
            else:
                raise Exception(f"No matching organization found for filing with {matching_field}='{entity_id}' in registry '{registry_id}'. User declined to create orphan organization.")
    elif len(matched_orgs) >= 2:
        logger.error(f"Database integrity error: Found {len(matched_orgs)} organizations matching {matching_field}='{entity_id}'")
        raise Exception(f"Database integrity error: Found {len(matched_orgs)} organizations matching {matching_field}='{entity_id}' in registry '{registry_id}'. Expected 0 or 1. Filing ID: {filing.get('_id', 'unknown')}")
    elif len(matched_orgs) == 1:
        [matched_org] = matched_orgs
        entity_id_mongo = matched_org['_id']

    result = mongo_regeindary[filings].update_one(
        {"_id": filing['_id']},
        {"$set": {"entityId_mongo": entity_id_mongo}}
    )
    return result


def run_all_match_filings(batch_size=False):
    """Match all unmatched filings to their corresponding organizations with progress tracking.

    Creates necessary indexes for performance, then iteratively processes unmatched filings.
    Displays progress updates every 5 minutes. Supports graceful interruption via Ctrl+C.

    Args:
        batch_size (int or False): Number of filings to match. If False, matches all unmatched
                                   filings. Defaults to False.
    """

    # - [ ] Turn into a Loop
    logger.info("Creating indexes for optimal matching performance")
    logger.debug(f"Index #1: organizations(registryID, entityIndex) - {datetime.now()}")
    index_check(mongo_regeindary[orgs], ['registryID', 'entityIndex'])
    logger.debug(f"Index #2: filings(entityId_mongo) - {datetime.now()}")
    index_check(mongo_regeindary[filings], ['entityId_mongo'])
    logger.debug(f"Index #3: organizations(registryID, entityId) - {datetime.now()}")
    index_check(mongo_regeindary[orgs], ['registryID', 'entityId'])

    unmatched_identifier = {"entityId_mongo": {"$exists": False}}
    matched_identifier = {"entityId_mongo": {"$exists": True}}

    if batch_size:
        logger.info(f"Starting batch matching operation for {batch_size:,} filings")
        n_unmatched = batch_size
    else:
        logger.info("Counting total filings...")
        n_total = mongo_regeindary[filings].count_documents(filter={}, hint="_id_")
        logger.info(f"Total filings: {n_total:,}")

        logger.info("Counting matched filings...")
        n_matched = mongo_regeindary[filings].count_documents(matched_identifier)
        logger.info(f"Already matched: {n_matched:,}")

        n_unmatched = n_total - n_matched
        logger.info(f"Unmatched filings to process: {n_unmatched:,}")


    reference_unmatched = n_unmatched
    reference_time = datetime.now()

    try:
        while n_unmatched > 0:
            print(f"\r  {n_unmatched:,} unmatched filings remaining".ljust(50), end="")
            filing = mongo_regeindary[filings].find_one(unmatched_identifier)

            if not filing:
                print("")
                logger.info("No unmatched filings found.")
                print(f"\r  No unmatched filings found.".ljust(50))
                break

            match_filing(filing)
            n_unmatched -= 1

            time_difference = datetime.now() - reference_time
            interval_minutes = 5
            if time_difference.total_seconds() > (interval_minutes * 60):
                unmatched_difference = reference_unmatched - n_unmatched
                logger.info(f"Progress update: {unmatched_difference:,} filings matched in last {interval_minutes} minutes")
                print(f"\n• {interval_minutes} minutes elapsed: {unmatched_difference:,} filings matched")
                reference_time = datetime.now()
                reference_unmatched = n_unmatched

        print(f"\r  All filings matched successfully!".ljust(50))
        logger.info("✔ Filing matching completed successfully")

    except KeyboardInterrupt:
        logger.warning("Matching process interrupted by user")
        print("\nMatching process stopped by user")


def completion_timestamp(meta_id, completion_type="download"):
    """Update registry metadata with completion timestamp.

    Args:
        meta_id (ObjectId): MongoDB ObjectId of the registry metadata document.
        completion_type (str): Type of completion to timestamp (e.g., "download"). Defaults to "download".

    Returns:
        UpdateResult: MongoDB update result object.
    """
    result = mongo_regeindary[meta].update_one(
        {
            "_id": meta_id
        },
        {
            "$set": {f"{completion_type}_completion": datetime.now()}
        }
    )

    return result


def get_random_entity(display=False, mongo_filter=None, hard_limit=False):
    """Retrieve a random organization entity from the database.

    Args:
        display (bool or str): If True, pretty-print the entity. If "No Original", exclude
                              "Original Data" field from output. Defaults to False.
        mongo_filter (dict, optional): MongoDB filter to constrain random selection. Defaults to None.
        hard_limit (int or False): Maximum number of documents to consider. Useful for large collections.
                                  Defaults to False.

    Returns:
        dict: Random organization document from the database.
    """
    logger.debug("Retrieving random organization entity from database")
    if mongo_filter is None:
        mongo_filter = {}
        hint = "_id_"
    else:
        hint = None
    limit = mongo_regeindary.organizations.count_documents(mongo_filter, hint=hint) + 1
    if hard_limit:
        if limit > hard_limit:
            limit = hard_limit
    random_select = random.randrange(0, limit)
    if display:
        print("Entity", random_select, "of", limit)
    random_entity = mongo_regeindary.organizations.find_one(mongo_filter, skip=random_select)
    if display:
        if display == "No Original":
            del random_entity['Original Data']
        (pp(random_entity))
    return random_entity


def get_all_urls(entity_id):
    # For future implementation -- this is the more "in-depth" path
    # Possible uses include: -- finding correct URLs if most recent is a dud/typo
    #                        -- using historical/redirect URLs in matching process
    z = mongo_regeindary[filings].find({"entityId_mongo": bson.ObjectId(entity_id)})
    u = set([x['websiteUrl'].lower() for x in z])
    print(u)
    return u


def get_most_recent_url(entity_id):
    z = mongo_regeindary[filings].aggregate([
        {"$match" : {"entityId_mongo": bson.ObjectId(entity_id)}},
        {"$project" : {"websiteUrl" : 1, 'recordDate' : 1}},
        {"$sort": {"recordDate": -1}},
        {"$limit" : 1}
    ])

    url = None
    for x in z:
        url = x['websiteUrl']
        if type(url) == float:
            url = None

    return url


def get_entities_that_need_websites(batch_size = False):
    print("Counting entities without websiteUrl listed...")
    missing_websites = mongo_regeindary[orgs].count_documents({"websiteUrl": {"$exists": False}})
    print(f"{missing_websites:,} entities have not been matched with a websiteUrl (or determined to have no match)")

    if batch_size:
        missing_websites = batch_size
    while missing_websites > 0:
        z = mongo_regeindary[orgs].find_one({"websiteUrl" : {"$exists" : False}})
        missing_website_id = z['_id']
        print(f"{missing_websites:,} remaining: mongoId of org without websiteUrl:", missing_website_id, end=" --> ")

        url = get_most_recent_url(missing_website_id)
        print("Matched URL: ", url)
        r = mongo_regeindary[orgs].update_one({"_id" : missing_website_id}, {"$set" : {"websiteUrl" : url}})

        missing_websites -= 1
