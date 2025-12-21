"""Data retrieval module for Australian charity registry (ACNC).

Downloads charity data from the Australian Charities and Not-for-profits Commission,
applies field mappings according to mapping.json, and uploads to MongoDB.
Registry metadata (including legal notices) loaded from metadata.json.
"""
import os
import sys
import logging

# Add the project root directory to sys.path if it's not already there
# This allows for same functionality in Anaconda Powershell as in Pycharm
project_root = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_root)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

import pandas as pd
from scripts.utils import *

logger = logging.getLogger(__name__)


# Functions
def retrieve_data(folder, metadata):
    """Download and parse Australian charity register data.

    Args:
        folder (str): Directory path for cache storage.
        metadata (dict): Registry metadata containing api_url.

    Returns:
        list: List of dictionaries containing charity records from Australia.
    """
    cached = check_for_cache(folder)
    api_url = metadata['api_url']

    if cached:
        logger.info("Loading data from cache")
        response_df = pd.read_csv(f"{folder}cache.csv", encoding_errors="backslashreplace",
                                  low_memory=False)  # Encoding error unique to Australia
    elif cached is False:
        # Structure -- Encoding error unique to Australia
        logger.info(f"Downloading Australian charity data from {api_url}")
        print("  Step 1/2: Downloading data into dataframe...")
        response_df = pd.read_csv(api_url, encoding_errors="backslashreplace")
        response_df.to_csv(f"{folder}cache.csv")
        logger.info(f"Data cached to {folder}cache.csv")
    else:
        logger.error(f"Unexpected cache state: {cached}")
        raise Exception(f"Unexpected cache state: cached={cached}. Expected True or False.")

    # Structure
    logger.info(f"Converting {len(response_df):,} records to dictionary format")
    print("  Step 2/2: Converting to dictionary format...")
    response_dicts = response_df.to_dict(orient="records")

    return response_dicts


def run_everything(folder=""):
    """Main orchestration function for retrieving and uploading Australian charity data.

    Downloads data from the Australian Charities and Not-for-profits Commission (ACNC),
    applies field mappings, and uploads to MongoDB. Legal notices are stored at the
    registry level (in metadata.json), not duplicated in each record.

    Args:
        folder (str): Directory path for cache and mapping files. Defaults to "".

    Returns:
        dict: Dictionary of MongoDB insert results indexed by record number.
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

    # Download Data
    raw_dicts = retrieve_data(folder, metadata)
    custom_mapping = retrieve_mapping(folder)

    # Register registry (stores legal notices at registry level, not in each record)
    meta_id, decision = register_registry(metadata)

    # Upload Data - legalNotices no longer duplicated in each record
    static_amendment = {
        "registryName": registry_name,
        "registryID": meta_id
    }

    logger.info(f"Retrieved {len(raw_dicts):,} records from source")
    print(f"  Retrieved {len(raw_dicts):,} records from source\n")

    # Handle different upload strategies based on user decision
    if decision == 's':
        logger.info("User chose to skip upload")
        print("✔ Upload skipped by user\n")
        return {}
    elif decision == 'i':
        logger.info("User chose incremental update - inserting only new records")
        final_results = send_new_to_mongodb(
            raw_dicts,
            custom_mapping,
            static_amendment,
            collection='organizations',
            unique_field='entityId'
        )
    else:
        # decision is 'y', 'n', or 0 (no existing records) - use normal batch insert
        final_results = send_all_to_mongodb(raw_dicts, custom_mapping, static_amendment)

    completion_timestamp(meta_id)
    logger.info(f"✔ {registry_name} data retrieval completed successfully")
    print("\n✔ Australia import complete\n")
    return final_results


if __name__ == '__main__':
    run_everything()
