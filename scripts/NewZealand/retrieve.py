"""Data retrieval module for New Zealand charity registry.

Downloads charity data from The Charities Register/Te Rēhita Kaupapa Atawhai
via OData API, applies field mappings, and uploads to MongoDB.
Registry metadata (including legal notices) loaded from metadata.json.
"""
from requests import get
from io import StringIO
import pandas as pd
from scripts.utils import *
import logging

logger = logging.getLogger(__name__)


def retrieve_data(folder, metadata):
    """Download and parse New Zealand charity register data from OData API.

    Args:
        folder (str): Directory path for cache storage.
        metadata (dict): Registry metadata containing api_url and headers.

    Returns:
        list: List of dictionaries containing charity records from New Zealand.
    """
    cached = check_for_cache(folder)
    api_url = metadata['api_url']
    headers = metadata.get('headers', {})

    if cached:
        logger.info("Loading data from cache")
        response_df = pd.read_csv(f"{folder}cache.csv", low_memory=False)  # Low Memory unique to New Zealand
    elif cached is False:
        # Request
        logger.info(f"Downloading New Zealand charity data from OData API")
        print("  Step 1/4: Downloading data from OData API...")
        response = get(api_url, headers=headers)

        # Format -- Unique to New Zealand
        logger.debug("Converting response to StringIO format")
        print("  Step 2/4: Formatting response data...")
        response_text = StringIO(response.text)

        # Structure
        logger.info("Parsing CSV data into dataframe")
        print("  Step 3/4: Parsing CSV data...")
        response_df = pd.read_csv(response_text, low_memory=False)
        response_df.to_csv(f"{folder}cache.csv")
        logger.info(f"Data cached to {folder}cache.csv")
    else:
        logger.error(f"Unexpected cache state: {cached}")
        raise Exception(f"Unexpected cache state: cached={cached}. Expected True or False.")

    # Structure
    logger.info(f"Converting {len(response_df):,} records to dictionary format")
    print("  Step 4/4: Converting to dictionary format...")
    response_dicts = response_df.to_dict(orient="records")

    return response_dicts


def run_everything(folder=""):
    """Main orchestration function for retrieving New Zealand charity data.

    Downloads data from The Charities Register/Te Rēhita Kaupapa Atawhai,
    applies field mappings, and uploads to MongoDB. Legal notices are stored
    at the registry level (in metadata.json), not duplicated in each record.

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
    meta_id, _ = register_registry(metadata)

    # Upload Data - legalNotices no longer duplicated in each record
    static_amendment = {
        "registryName": registry_name,
        "registryID": meta_id
    }
    logger.info(f"Retrieved {len(raw_dicts):,} records from source")
    print(f"  Retrieved {len(raw_dicts):,} records from source\n")
    final_results = send_all_to_mongodb(raw_dicts, custom_mapping, static_amendment)
    completion_timestamp(meta_id)
    logger.info(f"✔ {registry_name} data retrieval completed successfully")
    print("\n✔ New Zealand import complete\n")
    return final_results


if __name__ == '__main__':
    run_everything()
