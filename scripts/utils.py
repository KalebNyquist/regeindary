"""Core utility functions for Regeindary registry data aggregation.

This module provides MongoDB operations, field mapping, data upload, and entity-filing
matching functionality for importing heterogeneous civil society registry data into
a unified database structure.
"""
import inspect
import tomllib
import os
import pymongo
import json
from datetime import datetime
from pprint import pp
import random
import sys


# Add the project root directory to sys.path if it's not already there
project_root = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_root)
if parent_dir not in sys.path:
    print("Adding root")
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
    print(" Cache path:", cache_path)
    if os.path.exists(cache_path):
        print(" Cached file exists")
        cached = None
        while cached is None:
            option = input(" Download new copy? (y/n) ")
            if option.lower() == "y":
                cached = False
            elif option.lower() == "n":
                cached = True
            else:
                print(" Invalid option. Select `y` or `n`.")
    else:
        print(" Cached file does not exist")
        cached = False
    return cached


def delete_old_records(registry_id, collection='organizations'):
    """Check for existing records and prompt user to delete them.

    Args:
        registry_id (ObjectId): MongoDB ObjectId of the registry.
        collection (str): Collection name ('organizations' or 'filings'). Defaults to 'organizations'.

    Returns:
        str or int: 'y' if records deleted, 'n' or 's' if skipped, or 0 if no records exist.
    """
    global mongo_regeindary, collections_map

    record_count = mongo_regeindary[collections_map[collection]].count_documents({"registryID": registry_id})
    print("", record_count, "records associated with registry.")
    if record_count > 0:
        delete_option = None
        option = None
        while delete_option is None:
            option = input(" Delete old records? (y/n, or s to skip upload) ")
            if option.lower() == "y":
                delete_option = True
            elif (option.lower() == "n") or (option.lower() == "s"):
                delete_option = False
            else:
                print(" Invalid option. Select `y`, `n`, or `s`.")
        if delete_option:
            mongo_regeindary[collections_map[collection]].delete_many({"registryID": registry_id})
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
    for i, record in enumerate(records, start=1):
        if (i % 100 == 0) or (i == len(records)):
            percentage = "%.2f" % (100 * i/len(records))
            print(f"\r {i}/{len(records)} ({percentage}%) records transformed", end="")

        # Apply mapping transformation (same logic as send_to_mongodb)
        upload_dict = static.copy()
        for m in mapping.keys():
            if m in record.keys():
                upload_dict.update({mapping[m]: record[m]})
        upload_dict.update({"Original Data": record})
        upload_documents.append(upload_dict)

    print()  # New line after transformation progress

    # Batch insert all documents at once
    print(f" Inserting {len(upload_documents)} documents to MongoDB...", end="")
    result = mongo_regeindary[collections_map[collection]].insert_many(
        upload_documents,
        ordered=False  # Continue on error, more resilient for large batches
    )
    print(" ✔")

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
        print("", registry_name, "does not exist in collection. Creating now.")
        result = mongo_regeindary[meta].insert_one({
            "name": registry_name,
            "source": source_url
        })
        return result.inserted_id, None
    elif preexisting_registries == 1:
        print("", registry_name, "exists. Accessing now.")
        result = mongo_regeindary[meta].find_one({"name": registry_name})
        decision = delete_old_records(result['_id'], collection)
        return result['_id'], decision
    elif preexisting_registries >= 2:
        raise Exception(f"Database integrity error: Found {preexisting_registries} registries with name '{registry_name}'. Expected 0 or 1.")
    else:
        raise Exception(f"Unexpected database state: Registry count for '{registry_name}' is {preexisting_registries}. This should not be possible.")


def retrieve_mapping(folder=""):
    """Load field mapping from mapping.json file.

    Args:
        folder (str): Directory containing mapping.json. Defaults to current directory.

    Returns:
        dict: Dictionary mapping origin field names to target field names.
    """
    with open(f"{folder}mapping.json", "r") as m:
        mp = json.load(m)
    mapping = {feature['origin']: feature['target'] for feature in mp}
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

    print("Status Check Beginning")
    print("  Counting # Registries...", end="")
    n_registries = mongo_regeindary[meta].count_documents({}, hint="_id_")
    print(" ✔\n  Counting # Organizations...", end="")
    n_organizations = mongo_regeindary[orgs].count_documents({}, hint="_id_")
    print(" ✔\n  Counting # Filings...", end="")
    n_filings = mongo_regeindary[filings].count_documents({},  hint="_id_")
    print(" ✔")

    registries = list_registries()

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
    print(int(total_size), "bytes =", round((total_size / 1024 ** 3), 2), "gigabytes")


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
        print(options[select]["name"], "preselected")

    # MAIN FUNCTION
    directory = directory_map[options[select]["name"]]

    with open(f"{directory}/mapping.json", "r") as m:
        mapping = json.load(m)
    with open("../schemas/entity.json", "r") as s:
        schema = json.load(s)

    overlap = set.intersection(set([x['target'] for x in mapping]), set(schema['properties'].keys()))
    print("Schema fields already accounted for:", ", ".join(overlap))
    missing = set.difference(set(schema['properties'].keys()), set([x['target'] for x in mapping]))
    print("Schema fields not accounted for:", ", ".join(missing))

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
            entity_id_mongo = create_organization_from_orphan_filing(filing)
        else:
            print("⚠️ No matching organization found for filing (see below).")
            pp(filing)
            manual_decision = input("Create Organization from Orphan Filing? (y/n) ")
            if manual_decision == "y":
                entity_id_mongo = create_organization_from_orphan_filing(filing)
            else:
                raise Exception(f"No matching organization found for filing with {matching_field}='{entity_id}' in registry '{registry_id}'. User declined to create orphan organization.")
    elif len(matched_orgs) >= 2:
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
    print("Checking for Index #1 -", datetime.now())  # - [ ] this one can be deleted if UK/Wales resolved
    index_check(mongo_regeindary[orgs], ['registryID', 'entityIndex'])
    print("Checking for Index #2 -", datetime.now())
    index_check(mongo_regeindary[filings], ['entityId_mongo'])
    print("Checking for Index #3 -", datetime.now())
    index_check(mongo_regeindary[orgs], ['registryID', 'entityId'])

    unmatched_identifier = {"entityId_mongo": {"$exists": False}}
    matched_identifier = {"entityId_mongo": {"$exists": True}}

    if batch_size:
        print(f"Beginning a batch of {batch_size:,} filings at", datetime.now())
        n_unmatched = batch_size
    else:
        print(f"Counting All Filings - {datetime.now()}")
        n_total = mongo_regeindary[filings].count_documents(filter={}, hint="_id_")
        print(f"{n_total:,} existing as of {datetime.now()}")

        print(f"Counting Matched Filings - {datetime.now()}")
        n_matched = mongo_regeindary[filings].count_documents(matched_identifier)
        print(f"{n_matched:,} matched as of {datetime.now()}")

        print(f"Calculating Unmatched Filings - {datetime.now()}")
        n_unmatched = n_total - n_matched
        print(f"{n_unmatched:,} matched as of {datetime.now()}")


    reference_unmatched = n_unmatched
    reference_time = datetime.now()

    try:
        while n_unmatched > 0:
            print(f"\r{n_unmatched:,} unmatched at {datetime.now()}".ljust(50), end="")
            filing = mongo_regeindary[filings].find_one(unmatched_identifier)
            match_filing(filing)
            n_unmatched -= 1

            time_difference = datetime.now() - reference_time
            interval_minutes = 5
            if time_difference.total_seconds() > (interval_minutes * 60):
                unmatched_difference = reference_unmatched - n_unmatched
                print(f"• {interval_minutes} minutes have passed and {unmatched_difference} matches have been made")
                reference_time = datetime.now()
                reference_unmatched = n_unmatched

        print(f"\r{n_unmatched:,} unmatched at {datetime.now()}".ljust(50))
        print("✔ Complete!")

    except KeyboardInterrupt:
        print("Matching Process Stopped")


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
    print("Retrieving random entry")
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


if __name__ == '__main__':
    pass
