(
    baseUrl as text,
    optional keyword as nullable text,
    optional area as nullable text,
    optional jobsource as nullable text,
    optional mode as nullable text,
    optional order as nullable text,
    optional page as nullable number,
    optional pagesize as nullable number,
    optional jobcat as nullable text
) as record =>
let
    NormalizedBaseUrl = Text.Trim(baseUrl),
    ValidatedBaseUrl =
        if NormalizedBaseUrl = "" then
            error Error.Record(
                "Missing base URL",
                "baseUrl is required and cannot be empty.",
                null
            )
        else
            NormalizedBaseUrl,
    Configuration =
        #table(
            type table
            [
                baseUrl = text,
                keyword = nullable text,
                area = nullable text,
                jobsource = nullable text,
                mode = nullable text,
                order = nullable text,
                page = nullable number,
                pagesize = nullable number,
                jobcat = nullable text
            ],
            {
                {
                    ValidatedBaseUrl,
                    keyword,
                    area,
                    jobsource,
                    mode,
                    order,
                    page,
                    pagesize,
                    jobcat
                }
            }
        ),

    PythonOutput =
        Python.Execute(
"
import json
import math
import urllib.request
from datetime import datetime

import cloudscraper
import pandas as pd

config_row = config.iloc[0]

BASE_URL = str(config_row['baseUrl'])

def optional_text(value):
    if value is None or pd.isna(value):
        return None
    normalized = str(value).strip()
    return normalized if normalized else None

def optional_positive_int(value, field_name):
    if value is None or pd.isna(value):
        return None
    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f'{field_name} must be an integer when provided') from exc
    if not math.isfinite(numeric_value) or not numeric_value.is_integer():
        raise ValueError(f'{field_name} must be an integer when provided')
    normalized = int(numeric_value)
    if normalized < 1:
        raise ValueError(f'{field_name} must be greater than zero when provided')
    return normalized

KEYWORD = optional_text(config_row['keyword'])
AREA = optional_text(config_row['area'])
JOBSOURCE = optional_text(config_row['jobsource'])
MODE = optional_text(config_row['mode'])
ORDER = optional_text(config_row['order'])
PAGE = optional_positive_int(config_row['page'], 'page')
PAGE_SIZE = optional_positive_int(config_row['pagesize'], 'pagesize')
JOBCAT = optional_text(config_row['jobcat'])

optional_params = {
    'area': AREA,
    'jobsource': JOBSOURCE,
    'keyword': KEYWORD,
    'mode': MODE,
    'order': ORDER,
    'page': PAGE,
    'pagesize': PAGE_SIZE,
    'jobcat': JOBCAT,
}
params = {
    key: value
    for key, value in optional_params.items()
    if value is not None
}

headers = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://www.104.com.tw/jobs/search/',
}

system_proxies = urllib.request.getproxies()
valid_proxies = {
    key: value
    for key, value in system_proxies.items()
    if key.lower() in ('http', 'https')
}

scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True,
    }
)

if valid_proxies:
    scraper.proxies.update(valid_proxies)

snapshot_dt = datetime.now().astimezone()
snapshot_date = snapshot_dt.date().isoformat()
snapshot_datetime = snapshot_dt.isoformat(timespec='seconds')

try:
    response = scraper.get(
        BASE_URL,
        params=params,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
except Exception as exc:
    raise RuntimeError(
        f'104 API request failed for page={PAGE}, pagesize={PAGE_SIZE}: {exc}'
    ) from exc

try:
    json_data = response.json()
except ValueError as exc:
    raise RuntimeError(
        f'104 API returned invalid JSON for page={PAGE}: {exc}'
    ) from exc

if not isinstance(json_data, dict):
    raise TypeError(
        f'Expected the top-level JSON value to be an object; got {type(json_data).__name__}'
    )

jobs_list = json_data.get('data')
metadata_node = json_data.get('metadata')

if not isinstance(jobs_list, list):
    raise TypeError(
        f'Expected $.data to be an array; got {type(jobs_list).__name__}'
    )

if not isinstance(metadata_node, dict):
    raise TypeError(
        f'Expected $.metadata to be an object; got {type(metadata_node).__name__}'
    )

if any(not isinstance(job, dict) for job in jobs_list):
    raise TypeError('Expected every item in $.data to be an object')

df_jobs = pd.DataFrame(jobs_list)

def serialize_complex(value):
    if isinstance(value, (dict, list)):
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(',', ':'),
        )
    return value

for column_name in df_jobs.columns:
    df_jobs[column_name] = df_jobs[column_name].map(serialize_complex)

df_jobs['snapshotDate'] = snapshot_date
df_jobs['snapshotDateTime'] = snapshot_datetime
df_jobs['sourceKeyword'] = KEYWORD
df_jobs['sourceArea'] = AREA
df_jobs['sourceJobcat'] = JOBCAT
df_jobs['sourcePage'] = PAGE
df_jobs['sourcePageSize'] = PAGE_SIZE

pagination_node = metadata_node.get('pagination')
filter_query_node = metadata_node.get('filterQuery')
job_keys = sorted(
    {
        key
        for job in jobs_list
        for key in job.keys()
    }
)

metadata = {
    'httpStatus': response.status_code,
    'requestUrl': response.url,
    'snapshotDate': snapshot_date,
    'snapshotDateTime': snapshot_datetime,
    'keyword': KEYWORD,
    'area': AREA,
    'jobcat': JOBCAT,
    'jobsource': JOBSOURCE,
    'mode': MODE,
    'order': ORDER,
    'requestedPage': PAGE,
    'requestedPageSize': PAGE_SIZE,
    'returnedJobs': len(jobs_list),
    'topLevelKeys': json.dumps(list(json_data.keys()), ensure_ascii=False),
    'dataKeys': json.dumps(job_keys, ensure_ascii=False),
    'metadataKeys': json.dumps(list(metadata_node.keys()), ensure_ascii=False),
    'paginationJson': json.dumps(pagination_node, ensure_ascii=False),
    'filterQueryJson': json.dumps(filter_query_node, ensure_ascii=False),
    'rawMetadataJson': json.dumps(metadata_node, ensure_ascii=False),
    'count': pagination_node.get('count') if isinstance(pagination_node, dict) else None,
    'currentPage': pagination_node.get('currentPage') if isinstance(pagination_node, dict) else None,
    'lastPage': pagination_node.get('lastPage') if isinstance(pagination_node, dict) else None,
    'total': pagination_node.get('total') if isinstance(pagination_node, dict) else None,
}

df_metadata = pd.DataFrame([metadata])
df_raw_response = pd.DataFrame(
    [
        {
            'sourcePage': PAGE,
            'snapshotDateTime': snapshot_datetime,
            'rawResponseJson': json.dumps(json_data, ensure_ascii=False),
        }
    ]
)
",
            [config = Configuration]
        ),

    Jobs = PythonOutput{[Name = "df_jobs"]}[Value],
    Metadata = PythonOutput{[Name = "df_metadata"]}[Value],
    RawResponse = PythonOutput{[Name = "df_raw_response"]}[Value]
in
    [
        Jobs = Jobs,
        Metadata = Metadata,
        RawResponse = RawResponse
    ]
