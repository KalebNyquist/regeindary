"""Data retrieval module for England & Wales charity registry.

Downloads charity entities and filing data from the Charity Commission Register,
extracts from zipped JSON files on Azure blob storage, applies field mappings,
and uploads to MongoDB.
"""
from scripts.utils import *
from requests import get
from zipfile import ZipFile
import shutil
import os
import json

# Globals
api_retrieval_points = {
    "entities": {
        "url": "https://ccewuksprdoneregsadata1.blob.core.windows.net/data/json/publicextract.charity.zip",
        "filename": "publicextract.charity.json"
    },
    "filings": {
        "url": "https://ccewuksprdoneregsadata1.blob.core.windows.net/data/json/publicextract"
               ".charity_annual_return_history.zip",
        "filename": "publicextract.charity_annual_return_history.json"
    }
}
source_url = 'https://register-of-charities.charitycommission.gov.uk/en/register/full-register-download'
headers = {"user-agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0"}
registry_name = "England and Wales - Charity Commission Register of Charities"


def retrieve_data(folder, label):
    """Download and parse England & Wales charity data (entities or filings).

    Args:
        folder (str): Directory path for cache storage.
        label (str): Dataset type - either "entities" or "filings".

    Returns:
        list: List of dictionaries containing charity or filing records.
    """
    cached = check_for_cache(folder, label=label, suffix="json")

    print(f" Retrieving `{label}` dataset")

    if cached:
        print(" Skipping Steps 1-3: Retrieving cached copy")
    elif cached is False:
        print(" Step 1 of X: Retrieving zip file from source")
        retrieval_with_unzip(label)

    print(" Step 4 of X: Load JSON file")
    with open(f"{folder}cache_{label}.json", encoding="utf-8-sig") as js:
        response_dicts = json.load(js)

    return response_dicts


def retrieval_with_unzip(label):
    """Download, extract, and prepare zipped JSON data from Azure blob storage.

    Args:
        label (str): Dataset type - either "entities" or "filings".

    Raises:
        Exception: If HTTP status code is not 200.
    """
    api_retrieval_point = api_retrieval_points[label]

    zipped_download = get(api_retrieval_point["url"])

    if (sc := zipped_download.status_code) != 200:
        raise Exception(f"Actual Status Code {str(sc)} ≠ Expected Status Code 200")

    with open(f"cache_{label}.zip", 'wb') as zd:
        zd.write(zipped_download.content)
        zd.close()

    specific_file_name = api_retrieval_point["filename"]
    print(f" Step 2 of X: Extracting desired file `{specific_file_name}` from zip file")

    with ZipFile(f"cache_{label}.zip", 'r') as zf:
        zf.extractall("temp")
        zf.close()

    shutil.move("temp/{}".format(specific_file_name), os.getcwd())

    try:
        os.remove(f"cache_{label}.json")
        print(" Cache removed successfully")
    except OSError as error:
        print(error)
        print(" Cache cannot be removed, assumed to not exist")

    os.rename(specific_file_name, f"cache_{label}.json")

    print(" Step 3 of X: Cleanup of temporary files")
    os.rmdir("temp")
    os.remove(f"cache_{label}.zip")


def run_everything(folder=""):
    """Main orchestration function for retrieving England & Wales charity data.

    Processes both entities (charities) and filings (annual returns) from the
    Charity Commission Register. Applies field mappings and uploads to MongoDB.

    Args:
        folder (str): Directory path for cache and mapping files. Defaults to "".

    Returns:
        dict or None: Dictionary of MongoDB insert results, or None if user skips upload.
    """
    # Initiation Message
    print(f"Retrieving data from `{registry_name}`")

    # Entities
    print(f"Starting with entities...")
    # Download Data
    raw_dicts = retrieve_data(folder, label="entities")
    custom_mapping = retrieve_mapping(folder)
    meta_id, skip = meta_check(registry_name, source_url)

    # Upload Data
    static_amendment = {
        "registryName": registry_name,
        "registryID": meta_id
    }

    print("", len(raw_dicts), "records retrieved from original source file")
    final_results = None
    if skip != 's':
        final_results = send_all_to_mongodb(raw_dicts, custom_mapping, static_amendment)

    # Filings
    print("\nContinuing with filings...")
    raw_dicts = retrieve_data(folder, label="filings")
    meta_id, skip = meta_check(registry_name, source_url, collection="filings")

    print("", len(raw_dicts), "records retrieved from original source file")
    if skip != 's':
        final_results = send_all_to_mongodb(raw_dicts, custom_mapping, static_amendment, collection='filings')

    completion_timestamp(meta_id)
    print("\n ✔ Complete")
    return final_results


if __name__ == '__main__':
    run_everything()
