import pandas as pd

from scripts.utils import *
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime
import zipfile_deflate64 as zipfile  # - [ ] list as a dependency
from tqdm import tqdm  # For `download_file_with_progress()`
import warnings

# Globals
api_retrieval_points = {
    "entities": {
        "url": "https://www.irs.gov/pub/irs-soi/eo{i}.csv"
    },
    "filings": {
        "url": "https://www.irs.gov/charities-non-profits/form-990-series-downloads"  # technically a scrape...
        #  this is complicated by the Giving Tuesday Data Commons
    }
}


# Utils Candidates
def get_file_name(url_path):
    return url_path.split("/")[-1]


def download_file_with_progress(url, output_path):
    # - [ ] send this to utils?

    # Make the request with streaming enabled
    with requests.get(url, stream=True) as response:
        response.raise_for_status()  # Raise an error for bad status codes

        # Get the total file size from the headers (if available)
        total_size = int(response.headers.get('content-length', 0))

        # Open the output file for writing in binary mode
        with open(output_path, 'wb') as file:
            with tqdm(total=total_size, unit='B', unit_scale=True, desc='Downloading') as progress_bar:
                for chunk in response.iter_content(chunk_size=1024**2):
                    if chunk:  # Filter out keep-alive chunks
                        file.write(chunk)
                        progress_bar.update(len(chunk))


def retrieve_s3_files_metadata(s3_client, bucket_name, prefix):
    files = []
    paginator = s3_client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        if 'Contents' in page:
            for obj in page['Contents']:
                files.append(obj)
    return files


AWS_ACCESS_KEY_ID = None
AWS_SECRET_ACCESS_KEY = None


def establish_s3_client():
    import boto3
    global AWS_ACCESS_KEY_ID
    global AWS_SECRET_ACCESS_KEY

    if (AWS_ACCESS_KEY_ID is None) & (AWS_SECRET_ACCESS_KEY is None):
        AWS_ACCESS_KEY_ID = input("AWS Access Key ID: ")
        AWS_SECRET_ACCESS_KEY = input("AWS Secret Access Key: ")

    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

    return s3_client


source_url = 'https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf'
source_url_2 = 'https://www.irs.gov/charities-non-profits/form-990-series-downloads'  # - [ ] DO SOMETHING ABOUT THIS
headers = {"user-agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0"}
registry_name = "United States - Internal Revenue Service - Exempt Organizations Business Master File Extract"
filings_name = "United States - Form 990 Series"
directory_path = "zips_x"

# RETRIEVE ENTITIES
def retrieve_entities():
    # - [ ] can also grab directly from GivingTuesday DataCommons!

    print("Retrieving Entities")
    known_region_numbers = range(1, 5)
    # Region 1 = Northeast
    # Region 2 = Mid-Atlantic and Great Lakes
    # Region 3 = Gulf Coast and Pacific Coast
    # Region 4 = International and all others (i.e. Puerto Rico)
    # True as of December 8th 2024

    # Temporary Directory for Storing Regional Files
    os.mkdir("temp")
    os.mkdir("temp/eo_bmf")

    # Download Regional EO BMF files
    for i in known_region_numbers:
        print(f"\rDownloading Region {i} of {known_region_numbers[-1]} in master file")
        api_retrieval_point = api_retrieval_points["entities"]["url"].format(i=i)
        response = requests.get(api_retrieval_point)
        content = response.content.decode('utf-8')
        with open(f'temp/eo_bmf/eo{i}.csv', 'w') as eoX:
            eoX.write(content)

    # Combine Regional EO BMF files
    eo_master = None
    categorical_columns = ["EIN", "GROUP", "SUBSECTION", "AFFILIATION", "CLASSIFICATION", "RULING", "DEDUCTIBILITY",
                           'FOUNDATION', "ACTIVITY", "ORGANIZATION", "STATUS", "TAX_PERIOD", "ACCT_PD"]
    for i in known_region_numbers:
        print(f"\rAdding Region {i} of {known_region_numbers[-1]} to aggregation")
        eo_addition = pd.read_csv(f"temp/eo_bmf/eo{i}.csv", dtype={col: str for col in categorical_columns})
        # consider changing dtype to https://pandas.pydata.org/docs/reference/api/pandas.StringDtype.html

        if eo_master is None:
            eo_master = eo_addition
        elif type(eo_master) is pd.DataFrame:
            eo_master = pd.concat([eo_master, eo_addition], ignore_index=True)

    # Save master
    print("Saving Aggregation to Disk")
    eo_master.to_csv(f"cache_entities.csv", index=False)

    print("Converting to List of Dictionaries")
    eo_dicts = eo_master.to_dict(orient="records")

    # Clean-up
    print("Clean up")
    for i in known_region_numbers:
        os.remove(f'temp/eo_bmf/eo{i}.csv')
    os.rmdir("temp/eo_bmf")
    os.rmdir("temp")

    print("Complete")

    return eo_dicts  # - [ ] note inconsistency of index being included or excluded


# RETRIEVE FILINGS
# Note that the following three functions download all available 990s to disk.
# An alternative method is to use this URL: https://nccs-efile.s3.us-east-1.amazonaws.com/xml/{ObjectId}_public.xml
# This method downloads 990s à la carte.
# Above URL courtesy of https://github.com/Nonprofit-Open-Data-Collective/irs990efile

def retrieve_locations_of_filing_zips():
    """Creates a .csv file that contains links to each of the .zip files with 990 .xml files"""
    # This is a webscrape!
    # Corresponds with Jupyter Notebook "Core 0a0a" from earlier version of project

    # Get Webpage
    api_retrieval_point = api_retrieval_points['filings']['url']
    response = requests.get(api_retrieval_point)
    if response.status_code != 200:
        raise Exception(f"Status Code {response.status_code} is not 200 OK")

    # Beautiful Soup-ify for easier parsing
    def validate_record(record_to_validate):
        if record_to_validate.get_text(strip=True) == "":
            return False
        else:
            return True

    record_name = "li"
    record_attrs = {}
    soup = BeautifulSoup(response.content, "html.parser")

    def get_records_after_subheader_only(subheader):

        forward_records = set(subheader.find_all_next(record_name, record_attrs))
        next_subheader = subheader.find_next(subheader_name, subheader_attrs)

        if next_subheader:
            backward_records = set(next_subheader.find_all_previous(record_name, record_attrs))
            intersecting_records = forward_records.intersection(backward_records)
        elif next_subheader is None:
            intersecting_records = forward_records
        else:
            intersecting_records = forward_records

        # Reuses the validate record function defined above.
        intersecting_records = [r for r in intersecting_records if validate_record(r)]

        # Sometimes the subheaders are in tags that are similar to the records. This catches those instances.
        intersecting_records = [r for r in intersecting_records if
                                all(str(s) not in str(r) for s in [subheader, next_subheader])]

        return intersecting_records

    subheader_name = "h4"
    subheader_attrs = {}
    subheaders = soup.find_all(subheader_name, subheader_attrs)

    records = []

    for i_1, subheader in enumerate(subheaders):
        intersecting_records = get_records_after_subheader_only(subheader)
        for i_2, intersecting_record in enumerate(intersecting_records):
            print(i_1, i_2, end="\r".rjust(100))
            # subheader_copy = get_version_without_children(tag)
            # 💡 Note reversed concat order
            record_with_subheader = BeautifulSoup(str(intersecting_record) + str(subheader), features="html.parser")
            records.append(record_with_subheader)

    print(len(records))
    if len(records) == 0:
        raise Exception(f"{len(records)} records found, when at least one is expected. This suggests a blank page or "
                        f"incorrect element name+attrs")

    def parse_record(record, diagnostics=False):

        def get_value_by_tag(record, tag_name, tag_attrs, value_attr=None):

            tag = record.find(tag_name, tag_attrs)
            if tag is None:
                value = None
            elif value_attr is None:
                value = tag.get_text(separator=" ", strip=True)
            elif value_attr is not None:
                value = tag.attrs[value_attr]
            else:
                value = None

            return value

        row_dict = {

            "Year": get_value_by_tag(record, "h4", {}),
            "Name": get_value_by_tag(record, "a", {}),
            "URL": get_value_by_tag(record, "a", {}, "href")
            # "Description" : get_value_by_tag(record, "p")

        }

        if row_dict["Name"] is None:
            row_dict["Name"] = get_value_by_tag(record, "li", {})

        if diagnostics:
            row_dict["Raw Data"] = record

        return row_dict

    rows = []
    diagnostics = False
    for i, record in enumerate(records):

        try:
            row = parse_record(record, diagnostics=diagnostics)
            rows.append(row)
        except Exception as e:
            if diagnostics:
                print(i, str(e), record)

    df = pd.DataFrame(rows)

    # Filter Final Product
    df = df[df['Name'].apply(lambda x: x.removesuffix(" ZIP")) == df['URL']]

    # Export Final Product
    def get_filepath(scrape_url, annotation=False, timestamp_format="date"):

        parsed_url = urlparse(scrape_url)
        parsed_netloc = parsed_url.netloc.removeprefix("www.")
        parsed_path = parsed_url.path.replace("/", "_")

        filepath = parsed_netloc + parsed_path

        if timestamp_format == "date":
            timestamp = datetime.now().strftime("%Y-%m-%d")
        elif timestamp_format == "epoch":
            timestamp = round(datetime.now().timestamp())
        elif timestamp_format in [None, "none"]:
            timestamp = None
        else:
            print("⚠️ `timestamp_format` not recognized.")
            timestamp = None

        if annotation:
            filepath = filepath + "__" + str(annotation)

        if timestamp:
            filepath = filepath + "__" + str(timestamp)

        filepath = filepath + ".csv"

        return filepath

    export_filepath = get_filepath(scrape_url=api_retrieval_point, timestamp_format="date")
    df.to_csv(export_filepath, index=False, encoding="utf-8-sig")
    return export_filepath


def download_990s(locations):

    records = pd.read_csv(locations)
    records = records.to_dict(orient="records")

    # Download ZIP files

    # Ways to make this smarter:
    # - [ ] Add timestamps and calculate difference (how long does each download take?)
    # - [ ] Add stop/start functionality
    # - [ ] Add enumerate to know how far through everything
    # - [ ] Consider a "hard drive economical" version that processes and then deletes files
    for record in records:

        url = record['URL']
        print(url.ljust(100))
        file_name = get_file_name(url)

        z = 0
        response = requests.get(url, stream=True)
        print("Response received")
        with open(os.path.join(directory_path, file_name), 'wb') as out_file:
            for chunk in response.iter_content(chunk_size=512):
                out_file.write(chunk)
                # shutil.copyfileobj(response.raw, out_file)
                z += 1
                if z % 25000 == 0:
                    print(str(z).ljust(50), end="\r")
        print(file_name, "written".ljust(60))


def unzip_990s():
    directory_files = os.listdir(directory_path)

    def extract(file_name, year):
        file_path = os.path.join(directory_path, file_name)
        with zipfile.ZipFile(file_path, 'r') as zObject:
            zObject.extractall(path=os.path.join("filings", year))

    for i, file_name in enumerate(directory_files):
        file_name = get_file_name(file_name)
        year = file_name[0:4]  # - [ ] this won't always work, get from the spreadsheet instead
        datetime_now_str = datetime.now().isoformat().replace("T", " ").split(".")[0]
        print(f"[{i + 1}/{len(directory_files)}]", "Extracting", file_name, year, "•", datetime_now_str)
        extract(file_name, year)


# RETRIEVE FILINGS METADATA
def get_most_recent_index_GivingTuesday(cache=True):

    bucket_name = 'gt990datalake-rawdata'
    prefix = "Indices/990xmls/"

    if cache:
        return f"https://{bucket_name}.s3.amazonaws.com/{prefix}index_all_years_efiledata_xmls_created_on_2024-12-23.csv"

    s3_client = establish_s3_client()

    files = retrieve_s3_files_metadata(s3_client, bucket_name, prefix)
    files_df = pd.DataFrame(files)
    relevancy_mask = files_df['Key'].apply(lambda x: x.endswith('.csv') & ('index_all_years' in x))
    files_df = files_df[relevancy_mask].sort_values('LastModified', ascending=False)
    most_recent_file = files_df.iloc[0]
    most_recent_file_name = most_recent_file['Key']

    return f"https://{bucket_name}.s3.amazonaws.com/{most_recent_file_name}"


def get_most_recent_index_OfficialIRSWebsite():
    """Placeholder function with instructions to create a scrape of IRS Data,
    to be used as an alternative to Giving Tuesday
    """

    # Tax Years 2009-2020
    # - https://nccs-efile.s3.us-east-1.amazonaws.com/index/index-PX.csv  # 990 and 999EZ returns
    # - https://nccs-efile.s3.us-east-1.amazonaws.com/index/index-PF.csv  # 990PF returns
    # - The URLs can be constructed with the object ID and will thus look like:
    #           https://nccs-efile.s3.us-east-1.amazonaws.com/xml/201020793492001120_public.xml
    # - Source: https://github.com/Nonprofit-Open-Data-Collective/irs990efile (see bottom)

    # Tax Years 2020-2024
    # - Scrape: https://www.irs.gov/charities-non-profits/form-990-series-downloads-2020
    # - Scrape: https://www.irs.gov/charities-non-profits/form-990-series-downloads-2021
    # - Scrape: https://www.irs.gov/charities-non-profits/form-990-series-downloads-2022
    # - Scrape: https://www.irs.gov/charities-non-profits/form-990-series-downloads-2023
    # - Scrape: https://www.irs.gov/charities-non-profits/form-990-series-downloads-2024
    pass


# RUN EVERYTHING
# - [ ] This currently excludes the "RETRIEVE FILINGS" functions as part of the process
def run_everything(folder=""):
    # Initiation Message
    print(f"Retrieving data from `{registry_name}`")

    # Legal Notice
    # - [ ] Only true if not retrieving directly from IRS Website!
    # - [ ] This and other legal notices should be made part of the registry entry
    description = """
    Database Contents License (DbCL)

The Licensor and You agree as follows:

1.0 Definitions of Capitalised Words

The definitions of the Open Database License (ODbL) 1.0 are incorporated 
by reference into the Database Contents License.

2.0 Rights granted and Conditions of Use<

2.1 Rights granted. The Licensor grants to You a worldwide,
royalty-free, non-exclusive, perpetual, irrevocable copyright license to
do any act that is restricted by copyright over anything within the
Contents, whether in the original medium or any other. These rights
explicitly include commercial use, and do not exclude any field of
endeavour. These rights include, without limitation, the right to
sublicense the work.

2.2 Conditions of Use. You must comply with the ODbL.

2.3 Relationship to Databases and ODbL. This license does not cover any
Database Rights, Database copyright, or contract over the Contents as
part of the Database. Please see the ODbL covering the Database for more
details about Your rights and obligations.

2.4 Non-assertion of copyright over facts. The Licensor takes the
position that factual information is not covered by copyright. The DbCL
grants you permission for any information having copyright contained in
the Contents.

3.0 Warranties, disclaimer, and limitation of liability

3.1 The Contents are licensed by the Licensor “as is” and without any
warranty of any kind, either express or implied, whether of title, of
accuracy, of the presence of absence of errors, of fitness for purpose,
or otherwise. Some jurisdictions do not allow the exclusion of implied
warranties, so this exclusion may not apply to You.

3.2 Subject to any liability that may not be excluded or limited by law,
the Licensor is not liable for, and expressly excludes, all liability
for loss or damage however and whenever caused to anyone by any use
under this License, whether by You or by anyone else, and whether caused
by any fault on the part of the Licensor or not. This exclusion of
liability includes, but is not limited to, any special, incidental,
consequential, punitive, or exemplary damages. This exclusion applies
even if the Licensor has been advised of the possibility of such
damages.

3.3 If liability may not be excluded by law, it is limited to actual and
direct financial loss to the extent it is caused by proved negligence on
the part of the Licensor.
    """

    legal_notice = {
        "title": "Open Data Commons - Database Contents License (DbCL) v1.0",
        "description": description,
        "url": "https://opendatacommons.org/licenses/dbcl/1-0/"
    }

    # Entities
    print(f"Starting with entities...")
    # Download Data
    raw_dicts = retrieve_entities()
    custom_mapping = retrieve_mapping(folder)
    meta_id, skip = meta_check(registry_name, source_url)

    # Upload Data
    static_amendment = {
        "legalNotices": [legal_notice],
        "registryName": registry_name,
        "registryID": meta_id
    }

    print("", len(raw_dicts), "records retrieved from original source file")
    final_results = None

    if skip != 's':
        final_results = send_all_to_mongodb(raw_dicts, custom_mapping, static_amendment)

    # Filings Metadata
    print("\nContinuing with filings...")

    use_cache = {"AWS Path": True, "CSV File": True}
    if (use_cache['AWS Path'] is False) & (use_cache['CSV File'] is True):
        warnings.warn("Configured to retrieve a new file path but not download a new file.")

    index_url = get_most_recent_index_GivingTuesday(cache=use_cache['AWS Path'])
    if use_cache['CSV File'] is False:
        download_file_with_progress(index_url, "cache_filings_indices.csv")
    print("Loading filings metadata as List of Dictionaries")
    filings_metadata_dicts = pd.read_csv("cache_filings_indices.csv").to_dict(orient="records")

    print("", len(filings_metadata_dicts), "records retrieved from original source file")
    meta_id, skip = meta_check(registry_name, source_url, collection="filings")
    if skip != 's':
        final_results = send_all_to_mongodb(filings_metadata_dicts, custom_mapping, static_amendment, collection='filings')

    completion_timestamp(meta_id)
    print("\n ✔ Complete")

    return final_results


if __name__ == '__main__':
    run_everything()
