from requests import get
from io import StringIO
import pandas as pd
from scripts.utils import *

# Globals
api_retrieval_point = "http://www.odata.charities.govt.nz/Organisations?$format=csv&$returnall=true"
source_url = "https://www.charities.govt.nz/charities-in-new-zealand/the-charities-register/open-data/"
headers = {"user-agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0"}
registry_name = "New Zealand - The Charities Register/Te Rēhita Kaupapa Atawhai"


def retrieve_data(folder):
    cached = check_for_cache(folder)

    if cached:
        print(" Skipping Steps 1-3: Retrieving cached copy")
        response_df = pd.read_csv(f"{folder}cache.csv", low_memory=False)  # Low Memory unique to New Zealand
    elif cached is False:
        # Request
        print(f" Step 1 of 4: Downloading data from {api_retrieval_point}".ljust(50), end="\n")
        response = get(api_retrieval_point, headers=headers)

        # Format -- Unique to New Zealand
        print(f" Step 2 of 4: Formatting data as string".ljust(50), end="\n")
        response_text = StringIO(response.text)

        # Structure
        print(f" Step 3 of 4: Structuring data as dataframe".ljust(50), end="\n")
        response_df = pd.read_csv(response_text, low_memory=False)
        response_df.to_csv(f"{folder}cache.csv")
    else:
        raise Exception(f"Unexpected cache state: cached={cached}. Expected True or False.")

    # Structure
    print(f" Step 4 of 4: Structuring data as dicts".ljust(50), end="\n")
    response_dicts = response_df.to_dict(orient="records")

    return response_dicts


def run_everything(folder=""):
    # Initiation Message
    print(f"Retrieving data from `{registry_name}`")

    # Legal Notice
    description = ("The publication of email addresses on the Charities Register does not constitute deemed consent "
                   "for the purposes of the Unsolicited Electronic Messages Act 2007 "
                   "http://www.legislation.govt.nz/act/public/2007/0007/latest/DLM405134.html (which prohibits spam, "
                   "or unsolicited commercial electronic messages). You must not use this search function or the "
                   "Charities Register to obtain email addresses of charities for the purposes of marketing or "
                   "promoting goods or services, even where those goods or services are provided for free or at a "
                   "reduced price. For more information, visit the Department of Internal Affair’s anti-spam "
                   "webpages: https://www.dia.govt.nz/diawebsite.nsf/wpg_URL/Services-Anti-Spam-Index?OpenDocument")

    print(f" ⚠️️️ {description}")

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
    print("", len(raw_dicts), "records retrieved from original source file")
    final_results = send_all_to_mongodb(raw_dicts, custom_mapping, static_amendment)
    completion_timestamp(meta_id)
    print("\n ✔ Complete")
    return final_results


if __name__ == '__main__':
    run_everything()
