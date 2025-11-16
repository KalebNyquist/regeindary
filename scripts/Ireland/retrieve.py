"""Data retrieval module for Ireland charity registry.

Downloads charity entities and filing data from the Charities Regulator,
applies field mappings according to mapping.json, and uploads to MongoDB.
"""
from scripts.utils import *
from requests import get
import pandas as pd
import os
import logging

logger = logging.getLogger(__name__)

# Globals
api_retrieval_points = {
    "entities": "https://www.charitiesregulator.ie/media/d52jwriz/register-of-charities.csv",
    "filings": "https://www.charitiesregulator.ie/media/yeia3rfc/charity-annual-reports.csv"
}
source_url = 'https://data.gov.ie/dataset/register-of-charities-in-ireland'
headers = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
registry_name = "Ireland - Charities Regulator"


def retrieve_data(folder, label):
    """Download and parse Ireland charity data (entities or filings).

    Args:
        folder (str): Directory path for cache storage.
        label (str): Dataset type - either "entities" or "filings".

    Returns:
        list: List of dictionaries containing charity or filing records.
    """
    cached = check_for_cache(folder, label=label, suffix="csv")

    logger.info(f"Retrieving '{label}' dataset")

    if cached:
        logger.info("Loading data from cache")
    elif cached is False:
        logger.info(f"Downloading {label} data from Charities Regulator")
        print(f"  Step 1: Downloading {label} data...")
        download_csv(folder, label)

    logger.info(f"Loading CSV data from cache_{label}.csv")
    print(f"  Step 2: Loading CSV data...")

    # Try multiple encodings to handle Irish characters (fadas: á, é, í, ó, ú)
    for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
        try:
            response_df = pd.read_csv(f"{folder}/cache_{label}.csv", encoding=encoding, low_memory=False, header=1)
            logger.info(f"Successfully loaded CSV with {encoding} encoding")
            break
        except UnicodeDecodeError:
            logger.debug(f"Failed to load with {encoding} encoding")
            continue
    else:
        # If all encodings fail, use error handling
        logger.warning("All standard encodings failed, using error handling")
        response_df = pd.read_csv(f"{folder}/cache_{label}.csv", encoding='utf-8',
                                  encoding_errors='replace', low_memory=False, header=1)

    logger.info(f"Converting {len(response_df):,} records to dictionary format")
    response_dicts = response_df.to_dict(orient="records")

    logger.info(f"Loaded {len(response_dicts):,} {label} records")
    return response_dicts


def download_csv(folder, label):
    """Download CSV data from Charities Regulator.

    Attempts to download using pandas (which sometimes bypasses protections),
    falls back to requests library, and provides manual download instructions if both fail.

    Args:
        folder (str): Directory path for cache storage.
        label (str): Dataset type - either "entities" or "filings".

    Raises:
        Exception: If download fails with helpful instructions for manual download.
    """
    api_retrieval_point = api_retrieval_points[label]

    logger.info(f"Downloading from {api_retrieval_point}")

    # Try Method 1: Use pandas directly (sometimes bypasses Cloudflare)
    try:
        logger.debug("Attempting download via pandas.read_csv")
        # Try multiple encodings for Irish characters
        df = None
        for encoding in ['utf-8', 'latin-1', 'iso-8859-1']:
            try:
                df = pd.read_csv(api_retrieval_point, encoding=encoding,
                                storage_options={'User-Agent': headers['user-agent']}, header=1)
                logger.debug(f"Downloaded with {encoding} encoding")
                break
            except (UnicodeDecodeError, Exception):
                continue

        if df is None:
            raise Exception("Could not read CSV with any encoding")

        # Save as UTF-8 for consistency
        df.to_csv(f"{folder}cache_{label}.csv", index=False, encoding='utf-8')
        logger.info("Download complete via pandas")
        return
    except Exception as e:
        logger.debug(f"Pandas download failed: {e}")
        print(f"  ⚠️  Direct pandas download failed, trying requests library...")

    # Try Method 2: Use requests with enhanced headers
    try:
        enhanced_headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "accept-encoding": "gzip, deflate, br",
            "connection": "keep-alive",
            "upgrade-insecure-requests": "1",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none"
        }

        logger.debug("Attempting download via requests library")
        response = get(api_retrieval_point, headers=enhanced_headers, timeout=30)

        if (sc := response.status_code) != 200:
            logger.error(f"HTTP request failed with status code {sc}")
            raise Exception(f"Status code {sc}")

        logger.debug(f"Saving CSV data to cache_{label}.csv")
        with open(f"{folder}cache_{label}.csv", 'wb') as csv_file:
            csv_file.write(response.content)

        logger.info("Download complete via requests")
        return

    except Exception as e:
        logger.error(f"Automated download failed: {e}")

        # Provide manual download instructions
        print("\n" + "="*70)
        print("⚠️  AUTOMATED DOWNLOAD FAILED - MANUAL DOWNLOAD REQUIRED")
        print("="*70)
        print("\nThe website appears to be blocking automated downloads (likely Cloudflare).")
        print("\nPlease download the file manually:")
        print(f"  1. Open this URL in your browser:")
        print(f"     {api_retrieval_point}")
        print(f"\n  2. Save the downloaded file as:")
        print(f"     {os.path.abspath(folder)}cache_{label}.csv")
        print(f"\n  3. Re-run this script - it will use the cached file")
        print("="*70 + "\n")

        raise Exception(f"Download failed. Please download manually from: {api_retrieval_point}")


def run_everything(folder=""):
    """Main orchestration function for retrieving Ireland charity data.

    Processes both entities (charities) and filings (annual reports) from the
    Charities Regulator. Applies field mappings and uploads to MongoDB.

    Args:
        folder (str): Directory path for cache and mapping files. Defaults to "".

    Returns:
        dict or None: Dictionary of MongoDB insert results, or None if user skips upload.
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
                   "Attribution — You must give appropriate credit , provide a link to the license, and "
                   "indicate if changes were made. You may do so in any reasonable manner, but not in any way "
                   "that suggests the licensor endorses you or your use.\n"
                   "ShareAlike — If you remix, transform, or build upon the material, you must distribute "
                   "your contributions under the same license as the original.\n"
                   "No additional restrictions — You may not apply legal terms or technological measures that "
                   "legally restrict others from doing anything the license permits.")

    legal_notice = {
        "title": "Creative Commons Attribution 4.0 International",
        "description": description,
        "url": "https://creativecommons.org/licenses/by/4.0/"
    }

    # Entities
    logger.info("Phase 1: Processing charity entities")
    print("Phase 1: Processing Charity Entities")
    print("-" * 70)
    raw_dicts = retrieve_data(folder, label="entities")
    custom_mapping = retrieve_mapping(folder, level="entities")
    meta_id, skip = meta_check(registry_name, source_url)

    # Upload Data
    static_amendment = {
        "legalNotices": [legal_notice],
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
    print("Phase 2: Processing Charity Filings (Annual Reports)")
    print("-" * 70)
    raw_dicts = retrieve_data(folder, label="filings")
    custom_mapping = retrieve_mapping(folder, level="filings")
    meta_id, skip = meta_check(registry_name, source_url, collection="filings")

    logger.info(f"Retrieved {len(raw_dicts):,} filing records")
    print(f"  Retrieved {len(raw_dicts):,} filing records\n")
    if skip != 's':
        final_results = send_all_to_mongodb(raw_dicts, custom_mapping, static_amendment, collection='filings')

    completion_timestamp(meta_id)
    logger.info(f"✔ {registry_name} data retrieval completed successfully")
    print("\n✔ Ireland import complete\n")
    return final_results


if __name__ == '__main__':
    run_everything()
