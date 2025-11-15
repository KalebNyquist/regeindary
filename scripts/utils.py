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
    # - [ ] for performance, is there a way to rewrite this as "insert_many" rather than "insert_one"?
    results = {}
    for i, record in enumerate(records, start=1):
        if (i % 100 == 0) or (i == len(records)):
            percentage = "%.2f" % (100 * i/len(records))
            print(f"\r {i}/{len(records)} ({percentage}%) records processed", end="")
        result = send_to_mongodb(record, mapping, static, collection)
        results.update({i: result})

    return results


def send_to_mongodb(record, mapping, static, collection):
    global mongo_regeindary, collections_map
    upload_dict = static.copy()
    for m in mapping.keys():
        if m in record.keys():
            upload_dict.update({mapping[m]: record[m]})

    upload_dict.update({"Original Data": record})
    result = mongo_regeindary[collections_map[collection]].insert_one(upload_dict)

    return result


def meta_check(registry_name, source_url, collection="organizations"):
    """Checks to see if the registry is listed in the database. If it does not exist, it creates a listing and
    returns the id of the listing. If it does exist, it finds the listing and returns the id."""
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
    with open(f"{folder}mapping.json", "r") as m:
        mp = json.load(m)
    mapping = {feature['origin']: feature['target'] for feature in mp}
    return mapping


def list_registries():
    mongo_registries = mongo_regeindary[meta].find({})
    mongo_registries = [mongo_registry for mongo_registry in mongo_registries]
    return mongo_registries


def status_check():
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

    print(n_registries, "registries,", n_organizations, "organizations, and", n_filings, "filings")
    for registry in registries:
        # - [ ] consider replacing with a pipeline
        print(registry['name'].ljust(80, "."), end="")

        completion_time = registry.get("download_completion", False)
        if type(completion_time) is not bool:
            completion_time = datetime.strftime(completion_time, "%b %m %Y %H:%M")
        else:
            completion_time = "NOT COMPLETED YET"
        print(completion_time, end="...................")

        n_orgs_in_registry = mongo_regeindary[orgs].count_documents({'registryID': registry['_id']})
        fraction = n_orgs_in_registry / n_organizations
        percentage = round(fraction * 100, 2)
        percentage = f"{percentage}%"
        print(f"{n_orgs_in_registry} orgs ({percentage})".ljust(10), end="")
        n_filings_in_registry = mongo_regeindary[filings].count_documents({'registryID': registry['_id']})
        print(f" & {n_filings_in_registry} filings".ljust(30))

    total_size = mongo_regeindary.command("dbstats")['totalSize']
    print(int(total_size), "bytes =", round((total_size / 1024 ** 3), 2), "gigabytes")


def keyword_match_assist(select=None):

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
    desired_index = [(k, pymongo.ASCENDING) for k in identifiers]
    result = collection.create_index(desired_index)
    return result


def create_organization_from_orphan_filing(filing):

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
