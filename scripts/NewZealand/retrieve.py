"""Data retrieval module for New Zealand charity registry.

Downloads charity data from The Charities Register/Te Rēhita Kaupapa Atawhai
via OData API, applies field mappings, and uploads to MongoDB. Includes anti-spam
legal notice per Unsolicited Electronic Messages Act 2007.
"""
from requests import get
from io import StringIO
import pandas as pd
from scripts.utils import *
import logging

logger = logging.getLogger(__name__)

# Globals
api_retrieval_point = "http://www.odata.charities.govt.nz/Organisations?$format=csv&$returnall=true"
source_url = "https://www.charities.govt.nz/charities-in-new-zealand/the-charities-register/open-data/"
headers = {"user-agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0"}
registry_name = "New Zealand - The Charities Register/Te Rēhita Kaupapa Atawhai"


def retrieve_data(folder):
    """Download and parse New Zealand charity register data from OData API.

    Args:
        folder (str): Directory path for cache storage.

    Returns:
        list: List of dictionaries containing charity records from New Zealand.
    """
    cached = check_for_cache(folder)

    if cached:
        logger.info("Loading data from cache")
        response_df = pd.read_csv(f"{folder}cache.csv", low_memory=False)  # Low Memory unique to New Zealand
    elif cached is False:
        # Request
        logger.info(f"Downloading New Zealand charity data from OData API")
        print("  Step 1/4: Downloading data from OData API...")
        response = get(api_retrieval_point, headers=headers)

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
    applies field mappings, and uploads to MongoDB. Includes legal notice about
    email anti-spam requirements per the Unsolicited Electronic Messages Act 2007.

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
    description = ("The publication of email addresses on the Charities Register does not constitute deemed consent "
                   "for the purposes of the Unsolicited Electronic Messages Act 2007 "
                   "http://www.legislation.govt.nz/act/public/2007/0007/latest/DLM405134.html (which prohibits spam, "
                   "or unsolicited commercial electronic messages). You must not use this search function or the "
                   "Charities Register to obtain email addresses of charities for the purposes of marketing or "
                   "promoting goods or services, even where those goods or services are provided for free or at a "
                   "reduced price. For more information, visit the Department of Internal Affair's anti-spam "
                   "webpages: https://www.dia.govt.nz/diawebsite.nsf/wpg_URL/Services-Anti-Spam-Index?OpenDocument")

    logger.warning("Legal notice: Email addresses subject to Unsolicited Electronic Messages Act 2007")
    print(f"⚠️  LEGAL NOTICE - Unsolicited Electronic Messages Act 2007")
    print(f"{'-'*70}")
    print(f"Email addresses on this register may NOT be used for marketing/spam.")
    print(f"See: https://www.dia.govt.nz/diawebsite.nsf/wpg_URL/Services-Anti-Spam-Index")
    print(f"{'-'*70}\n")

    legal_notice = {
        "function": "No Email Solicitation",
        "title": "Unsolicited Electronic Messages Act 2007",
        "description": description
    }

    # Download Data
    raw_dicts = retrieve_data(folder)
    custom_mapping = retrieve_mapping(folder)
    # mongo_regeindary, collections_map = get_mongo_dbs()
    meta_id, _ = meta_check(registry_name, source_url)

    # Upload Data
    static_amendment = {
        "legalNotices": [legal_notice],
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
