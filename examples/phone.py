import os
import re
import time
import json
import colorlog
import requests
import logging
import pandas as pd
import lxml
import amazon_scrape_toolkit as ast
import bs4

color_stdout = logging.StreamHandler()
color_stdout.setFormatter(
    colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            "DEBUG": "blue",
            "INFO": "white",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )
)

# Add the handlers to the logger
logger = logging.getLogger()
logger.addHandler(color_stdout)
logger.setLevel(logging.INFO)

HEADERS = ast.AmazonHeaders(
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "en-US",
)


def fetch_webpage(url):
    response = session.get(url, headers=HEADERS.req)
    response.raise_for_status()
    return response.content


if not os.path.exists("raw.json"):
    with open("raw.json", "w", newline="") as csvfile:
        pass

try:
    existing = pd.read_json("../data/raw.json")
    existing.set_index(keys=["product_id"], inplace=True)
    existing_indices = list(set(existing.index.values.tolist()))
except:
    existing_indices = []

start_time = time.monotonic()
fetch_times = []

session = requests.Session()
failed = failed_reasons = []
scraped_ids = []


@ast.product_scraper(get_others=False)
def extract_product_info(soup, product_id):
    product_info = {"product_id": product_id}

    compare_table = soup.find("table", {"id": "HLCXComparisonTable"})
    try:
        mrp = float(
            soup.find("span", class_="a-price-whole").text.strip().replace(",", "")
        )
        model_name = str(soup.find("span", {"id": "productTitle"}).text.strip())
    except AttributeError as e:
        failed.append(product_id)
        failed_reasons.append(str(e))
        return

    product_info["mrp"] = mrp
    product_info["model_name"] = model_name.replace("|", "(").split("(")[0]

    if "(renewed)" in model_name.lower():
        logger.warn(f"PRODUCT IS RENEWED TYPE {product_id}")
        return

    if product_id in existing_indices:
        logger.warn(f"PRODUCT IS EXISTING TYPE {product_id}")
        return

    # --------- MINI INFO TABLE

    mini_table = {}
    table = soup.find("table", {"class": "a-normal a-spacing-micro"})

    if isinstance(table, bs4.Tag):
        for row in table.find_all("tr"):
            key = row.find("td", {"class": "a-span3"}).text.strip()
            value = row.find("td", {"class": "a-span9"}).text.strip()

            if key == "Model Name":
                product_info["model_name"] = value
                continue

            mini_table[key.lower()] = value

    # --------- PRODUCT SPECS TABLE

    product_spec_table = {}
    table = soup.find("table", {"id": "productDetails_techSpec_section_1"})
    if isinstance(table, bs4.Tag):
        for row in table.find_all("tr"):
            key = row.find("th").text.strip()
            value = row.find("td").text.strip()
            value = value.replace("\u200e", "")
            product_spec_table[key.lower()] = value

    # --------- COMPARE TABLE PHONE INFO

    compare_table_info = {}
    phone_info_rows = (
        compare_table.find_all("tr")[6:] if isinstance(compare_table, bs4.Tag) else []
    )
    for row in phone_info_rows:
        assert isinstance(row, bs4.Tag)
        property_value = row.find("td")

        if property_value is None:
            continue

        property_tag = row.find("th").find("span")
        assert isinstance(property_tag, bs4.Tag)
        property_name = property_tag.text.strip()
        property_value = property_value.text.strip()
        compare_table_info[property_name.lower()] = property_value

    # --------- EXTRACTING DATA FROM PAGE

    # so far we have mrp and model_name
    # and containers of mini_table, product_spec_table, compare_table_info
    logger.debug(f"MINI TABLE KEYS: {list(mini_table.keys())}")
    logger.debug(f"PRODUCT SPEC TABLE KEYS: {list(product_spec_table.keys())}")
    logger.debug(f"COMPARE TABLE KEYS: {list(compare_table_info.keys())}")

    product_info.update(mini_table)
    product_info.update(product_spec_table)
    product_info.update(compare_table_info)

    return product_info


all_phones = ast.get_all_products_data(
    "https://www.amazon.in/s?rh=n%3A1805560031&fs=true&ref=lp_1805560031_sar",
    extract_product_info,
    HEADERS,
    pages_to_scrape=1,
)

with open("raw.json", "r") as file:
    try:
        data = json.load(file)
    except:
        data = []

    current_no_of_rows = len(data)

# Append a variable containing a list of objects
finalized_new_phones = [
    phone
    for phone in all_phones
    if isinstance(phone, dict)
    and phone["product_id"] not in existing_indices
    and phone not in data
]
data.extend(finalized_new_phones)
new_no_of_rows = len(data)

# Save the updated data back to the original file
with open("raw.json", "w") as file:
    json.dump(data, file, indent=4)

failed_reasons = list(filter(lambda x: isinstance(x, str), failed_reasons))

logger.info("Total Time: %s", time.monotonic() - start_time)
logger.info("TIME FOR FETCHING: %s", fetch_times)
logger.info(
    "AVG TIME FOR FETCHING: %s",
    sum(fetch_times) / len(fetch_times) if len(fetch_times) > 0 else "NA",
)
logger.info(
    "NEWLY ADDED %s ROWS",
    len(finalized_new_phones),
)
logger.info("FAILED %s ROWS", len(failed))
logger.info("OLD NO OF ROWS: %s", current_no_of_rows)
logger.info("NEW NO OF ROWS: %s", new_no_of_rows)
logger.info("FAILED REASONS: %s", failed_reasons)
logger.info(
    "MAJOR FAILED REASON: %s",
    [
        (value, failed_reasons.count(value))
        for value in sorted(
            list(set(failed_reasons)),
            key=lambda reason: failed_reasons.count(reason),
            reverse=True,
        )
    ],
)
