import os
import sys

# Add the project root directory to sys.path if it's not already there
# This allows for same functionality in Anaconda Powershell as in Pycharm
project_root = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_root)
if parent_dir not in sys.path:
    print("Adding root")
    sys.path.append(parent_dir)

import pandas as pd
from scripts.utils import *

# Globals
api_retrieval_point = ("https://data.gov.au/data/dataset/b050b242-4487-4306-abf5-07ca073e5594/resource/8fb32972-24e9"
                       "-4c95-885e-7140be51be8a/download/datadotgov_main.csv")
source_url = 'https://data.gov.au/dataset/ds-dga-b050b242-4487-4306-abf5-07ca073e5594/details?q=acnc'
headers = {"user-agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0"}
registry_name = "Australia - ACNC Charity Register"


# Functions
def retrieve_data(folder):
    cached = check_for_cache(folder)

    if cached:
        print(" Skipping Step 1: Retrieving cached copy")
        response_df = pd.read_csv(f"{folder}cache.csv", encoding_errors="backslashreplace",
                                  low_memory=False)  # Encoding error unique to Australia
    elif cached is False:
        # Structure -- Encoding error unique to Australia
        print(f" Step 1 of 2: Downloading data into a dataframe".ljust(50), end="\n")
        response_df = pd.read_csv(api_retrieval_point, encoding_errors="backslashreplace")
        response_df.to_csv(f"{folder}cache.csv")
    else:
        raise Exception(f"Unexpected cache state: cached={cached}. Expected True or False.")

    # Structure
    print(" Step 2 of 2: Structuring data as dicts".ljust(50), end="\n")
    response_dicts = response_df.to_dict(orient="records")

    return response_dicts


def run_everything(folder=""):
    # Initiation Message
    print(f"Retrieving data from `{registry_name}`")

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
    meta_id, _ = meta_check(registry_name, source_url)

    # Upload Data
    static_amendment = {
        "legalNotices": [legal_notice],
        "registryName": registry_name,
        "registryID": meta_id
    }

    print("", len(raw_dicts), "records retrieved from original source file")
    final_results = send_all_to_mongodb(raw_dicts, custom_mapping, static_amendment)

    completion_timestamp(meta_id)
    print("\n ✔ Complete")
    return final_results


if __name__ == '__main__':
    run_everything()
