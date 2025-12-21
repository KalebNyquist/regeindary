"""Data retrieval module for England & Wales charity registry.

Downloads charity entities and filing data from the Charity Commission Register,
extracts from zipped JSON files on Azure blob storage, applies field mappings,
and uploads to MongoDB. Registry metadata (including legal notices) loaded from metadata.json.
"""
from scripts.utils import *
from requests import get
from zipfile import ZipFile
import shutil
import os
import json
import logging

logger = logging.getLogger(__name__)


def retrieve_data(folder, metadata, label):
    """Download and parse England & Wales charity data (entities or filings).

    Args:
        folder (str): Directory path for cache storage.
        metadata (dict): Registry metadata containing api_endpoints.
        label (str): Dataset type - either "entities" or "filings".

    Returns:
        list: List of dictionaries containing charity or filing records.
    """
    cached = check_for_cache(folder, label=label, suffix="json")

    logger.info(f"Retrieving '{label}' dataset")

    if cached:
        logger.info("Loading data from cache")
    elif cached is False:
        logger.info(f"Downloading {label} data from Azure blob storage")
        print(f"  Step 1: Downloading and extracting {label} data...")
        retrieval_with_unzip(metadata, label)

    logger.info(f"Loading JSON data from cache_{label}.json")
    print(f"  Step 2: Loading JSON data...")
    with open(f"{folder}cache_{label}.json", encoding="utf-8-sig") as js:
        response_dicts = json.load(js)

    logger.info(f"Loaded {len(response_dicts):,} {label} records")
    return response_dicts


def retrieval_with_unzip(metadata, label):
    """Download, extract, and prepare zipped JSON data from Azure blob storage.

    Args:
        metadata (dict): Registry metadata containing api_endpoints.
        label (str): Dataset type - either "entities" or "filings".

    Raises:
        Exception: If HTTP status code is not 200.
    """
    api_endpoint = metadata['api_endpoints'][label]

    logger.info(f"Downloading from {api_endpoint['url']}")
    zipped_download = get(api_endpoint["url"])

    if (sc := zipped_download.status_code) != 200:
        logger.error(f"HTTP request failed with status code {sc}")
        raise Exception(f"Actual Status Code {str(sc)} ≠ Expected Status Code 200")

    logger.debug(f"Saving zipped data to cache_{label}.zip")
    with open(f"cache_{label}.zip", 'wb') as zd:
        zd.write(zipped_download.content)
        zd.close()

    specific_file_name = api_endpoint["filename"]
    logger.info(f"Extracting {specific_file_name} from zip archive")

    with ZipFile(f"cache_{label}.zip", 'r') as zf:
        zf.extractall("temp")
        zf.close()

    shutil.move("temp/{}".format(specific_file_name), os.getcwd())

    try:
        os.remove(f"cache_{label}.json")
        logger.debug("Removed old cache file")
    except OSError as error:
        logger.debug(f"No old cache file to remove: {error}")

    os.rename(specific_file_name, f"cache_{label}.json")

    logger.debug("Cleaning up temporary files")
    os.rmdir("temp")
    os.remove(f"cache_{label}.zip")
    logger.info("Download and extraction complete")


def run_everything(folder=""):
    """Main orchestration function for retrieving England & Wales charity data.

    Processes both entities (charities) and filings (annual returns) from the
    Charity Commission Register. Applies field mappings and uploads to MongoDB.
    Legal notices are stored at the registry level (in metadata.json).

    Args:
        folder (str): Directory path for cache and mapping files. Defaults to "".

    Returns:
        dict or None: Dictionary of MongoDB insert results, or None if user skips upload.
    """
    # Load registry metadata from metadata.json
    metadata = load_registry_metadata(folder)
    registry_name = metadata['name']

    # Initiation Message
    logger.info(f"========== Starting {registry_name} data retrieval ==========")
    print(f"\n{'='*70}")
    print(f"Retrieving data from: {registry_name}")
    print(f"{'='*70}\n")

    # Display legal notices (stored in metadata.json, saved to registry collection)
    display_legal_notices(metadata.get('legal_notices', []))

    # Entities
    logger.info("Phase 1: Processing charity entities")
    print("Phase 1: Processing Charity Entities")
    print("-" * 70)
    raw_dicts = retrieve_data(folder, metadata, label="entities")
    custom_mapping = retrieve_mapping(folder)

    # Register registry (stores legal notices at registry level, not in each record)
    meta_id, skip = register_registry(metadata)

    # Upload Data - legalNotices no longer duplicated in each record
    static_amendment = {
        "registryName": registry_name,
        "registryID": meta_id
    }

    logger.info(f"Retrieved {len(raw_dicts):,} entity records")
    print(f"  Retrieved {len(raw_dicts):,} entity records\n")
    final_results = None
    if skip != 's':
        final_results = send_all_to_mongodb(raw_dicts, custom_mapping, static_amendment)

    # Filings
    logger.info("Phase 2: Processing charity filings")
    print(f"\n{'='*70}")
    print("Phase 2: Processing Charity Filings (Annual Returns)")
    print("-" * 70)
    raw_dicts = retrieve_data(folder, metadata, label="filings")
    meta_id, skip = register_registry(metadata, collection="filings")

    logger.info(f"Retrieved {len(raw_dicts):,} filing records")
    print(f"  Retrieved {len(raw_dicts):,} filing records\n")
    if skip != 's':
        final_results = send_all_to_mongodb(raw_dicts, custom_mapping, static_amendment, collection='filings')

    completion_timestamp(meta_id)
    logger.info(f"✔ {registry_name} data retrieval completed successfully")
    print("\n✔ England & Wales import complete\n")
    return final_results


if __name__ == '__main__':
    run_everything()
