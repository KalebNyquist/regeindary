"""Data retrieval module for Australian charity registry (ACNC).

Downloads charity data from the Australian Charities and Not-for-profits Commission,
applies field mappings according to mapping.json, and uploads to MongoDB.
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

# Globals
api_retrieval_point = ("https://data.gov.au/data/dataset/b050b242-4487-4306-abf5-07ca073e5594/resource/8fb32972-24e9"
                       "-4c95-885e-7140be51be8a/download/datadotgov_main.csv")
source_url = 'https://data.gov.au/dataset/ds-dga-b050b242-4487-4306-abf5-07ca073e5594/details?q=acnc'
headers = {"user-agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0"}
registry_name = "Australia - ACNC Charity Register"


# Functions
def retrieve_data(folder):
    """Download and parse Australian charity register data.

    Args:
        folder (str): Directory path for cache storage.

    Returns:
        list: List of dictionaries containing charity records from Australia.
    """
    cached = check_for_cache(folder)

    if cached:
        logger.info("Loading data from cache")
        response_df = pd.read_csv(f"{folder}cache.csv", encoding_errors="backslashreplace",
                                  low_memory=False)  # Encoding error unique to Australia
    elif cached is False:
        # Structure -- Encoding error unique to Australia
        logger.info(f"Downloading Australian charity data from {api_retrieval_point}")
        print("  Step 1/2: Downloading data into dataframe...")
        response_df = pd.read_csv(api_retrieval_point, encoding_errors="backslashreplace")
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
    applies field mappings, and uploads to MongoDB with legal notice metadata.

    Args:
        folder (str): Directory path for cache and mapping files. Defaults to "".

    Returns:
        dict: Dictionary of MongoDB insert results indexed by record number.
    """
    # Initiation Message
    logger.info(f"========== Starting {registry_name} data retrieval ==========")
    print(f"\n{'='*70}")
    print(f"Retrieving data from: {registry_name}")
    print(f"{'='*70}\n")

    # Legal Notice
    description = ("You are free to:\n"
                   "Share — copy and redistribute the material in any medium or format for any purpose, "
                   "even commercially.\n"
                   "Adapt — remix, transform, and build upon the material for any purpose, even commercially.\n"
                   "The licensor cannot revoke these freedoms as long as you follow the license terms.\n"
                   "Under the following terms:\n"
                   "Attribution — You must give appropriate credit, provide a link to the license, and indicate if "
                   "changes were made. You may do so in any reasonable manner, but not in any way that suggests the "
                   "licensor endorses you or your use.\n"
                   "No additional restrictions — You may not apply legal terms or technological measures that legally "
                   "restrict others from doing anything the license permits.")

    legal_notice = {
        "title": "Creative Commons Attribution 3.0 Australia",
        "description": description,
        "url": "https://creativecommons.org/licenses/by/3.0/au/"
    }

    # Download Data
    raw_dicts = retrieve_data(folder)
    custom_mapping = retrieve_mapping(folder)
    meta_id, decision = meta_check(registry_name, source_url)

    # Upload Data
    static_amendment = {
        "legalNotices": [legal_notice],
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
    elif decision == 'u':
        logger.info("User chose refresh/update - updating existing records while preserving MongoDB _id")
        final_results = refresh_all_to_mongodb(
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
