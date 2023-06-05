import re
import bs4
import time
import json
import logging
from functools import wraps
from dataclasses import dataclass
import requests


@dataclass
class AmazonHeaders:
    """Data class representing the headers for making requests to Amazon"""

    user_agent: str
    accept_lang: str
    accept: str

    @property
    def req(self):
        """
        Get the headers as a dictionary for the requests library.

        Returns:
            dict: The headers for making requests.
        """

        return {
            "User-Agent": self.user_agent,
            "Accept-Language": self.accept_lang,
            "Accept": self.accept,
        }


@dataclass
class ProductInfo:
    """Data class representing the information of a product"""

    other_products: list[str]
    ratings: dict[str:int]
    data: dict
    custom_scraper_time_taken: float
    ratings_scraper_time_taken: float
    more_phones_scraper_time_taken: float


def timer():
    """
    Generator function to measure the elapsed time.

    Yields:
        float: The start time.
        float: The time difference between start and yield.
    """

    start_time = time.monotonic()
    yield start_time
    yield round(time.monotonic() - start_time, 3)


def get_all_product_ids(link: str, headers: AmazonHeaders, max_products=10000000000000):
    """
    Fetches all product IDs from the given Amazon search link.

    Args:
        link (str): The Amazon search link.
        headers (AmazonHeaders): The headers to be used for making requests.
        max_products (int, optional): The maximum number of products to fetch. Defaults to As many as possible (10000000000000).

    Returns:
        set[str]: A set of product IDs.
    """
    pattern = (
        r"^https:\/\/www\.amazon\.[a-z]{2,}\/s\?rh=n%3A\d+&fs=true&ref=lp_\d+_sar$"
    )
    assert re.match(pattern, link), "Link Pattern is Incorrect for this Method"

    session = requests.Session()
    page_link = link
    no_of_pages = 0

    fetch_times = []
    start_time = time.monotonic()
    soup_pages = []

    try:
        for _ in set(range(max_products)):
            fetch_timer = timer()
            next(fetch_timer)

            no_of_pages += 1
            page = session.get(page_link, headers=headers.req)
            page.raise_for_status()

            fetch_times.append(next(fetch_timer))

            soup = bs4.BeautifulSoup(page.content, "lxml")
            next_page_a = soup.select_one("a.s-pagination-next")

            if next_page_a is None:
                current_page = soup.select_one(
                    "span.s-pagination-item.s-pagination-selected"
                )
                next_page_a = current_page.find_next_sibling(
                    "a", class_="s-pagination-item s-pagination-button"
                )

            page_link = f"https://www.amazon.in{next_page_a['href']}"
            soup_pages.append(soup)

    except (TypeError, AttributeError):
        logging.warn(f"final_page: {page_link}")

    logging.info(f"full fetch duration: {time.monotonic() - start_time}")
    logging.info(f"scraped {no_of_pages} pages")
    logging.debug(f"avg page fetch time: {sum(fetch_times) / len(fetch_times)}")
    logging.debug(f"max page fetch time: {max(fetch_times)}")
    logging.debug(f"min page fetch time: {min(fetch_times)}")

    scrape_timer = timer()
    next(scrape_timer)
    all_product_ids = []
    scrape_times = []

    def scrape_soup_links(soup: bs4.BeautifulSoup):
        st = time.monotonic()
        divs = soup.select("div[data-asin]")
        product_ids = filter(lambda x: x != "", [div["data-asin"] for div in divs])
        all_product_ids.extend(product_ids)
        scrape_times.append(time.monotonic() - st)

    [scrape_soup_links(soup) for soup in set(soup_pages)]

    logging.info(f"full scrape duration: {next(scrape_timer)}")
    logging.info(f"scraped {len(all_product_ids)} product id's")
    logging.info(f"but only {len(set(all_product_ids))} product id's are unique")
    logging.debug(f"avg page half scrape time: {sum(scrape_times) / len(scrape_times)}")
    logging.debug(f"max page half scrape time: {max(scrape_times)}")
    logging.debug(f"min page half scrape time: {min(scrape_times)}")

    return set(all_product_ids)


def product_scraper(fetch_ratings: bool = True, get_others: bool = True):
    """
    Decorator to mark a function as a product scraper.

    Args:
        fetch_ratings (bool, optional): Whether to fetch the ratings. Defaults to True.
        get_others (bool, optional): Whether to fetch information about other related products. Defaults to True.

    Returns:
        function: The decorated function.
    """

    def inner_decorator(func):
        @wraps(func)
        def _wrapper(soup: bs4.BeautifulSoup, product_id: str, *args, **kwargs):
            data_func_timer = timer()
            next(data_func_timer)
            data = func(soup, product_id, *args, **kwargs)
            assert isinstance(data, (dict, None)), "Output should be Dict or None!"

            if data is None:
                logging.info(f"page_failed [{product_id}]")
                return None

            data_func_timer = next(data_func_timer)
            new_phones_to_add = [] if get_others else None

            other_phones_fetch_timer = timer()
            next(other_phones_fetch_timer)
            if get_others:
                compare_table = soup.find("table", {"id": "HLCXComparisonTable"})

                if isinstance(compare_table, bs4.Tag):
                    compare_table_trs = compare_table.find(
                        "tr", class_="comparison_table_image_row"
                    )
                    assert isinstance(
                        compare_table_trs, bs4.Tag
                    ), "Compare Table doesnt contain TR"

                    new_phones = [
                        a_tag["href"] for a_tag in compare_table_trs.find_all("a")
                    ][1:]

                    for phone in set(new_phones):
                        match = re.search(r"/dp/([A-Z0-9]+)", phone)

                        if not match:
                            continue

                        competitor_id = match.group(1)
                        new_phones_to_add.append(competitor_id)

                    new_phones_to_add.extend(set(new_phones_to_add))

                new_phones_to_add.extend(
                    filter(
                        lambda x: x not in ["", product_id],
                        [div["data-asin"] for div in soup.select("div[data-asin]")],
                    )
                )
                new_phones_to_add = list(set(new_phones_to_add))
            other_phones_fetch_timer = next(other_phones_fetch_timer)

            # get ratings
            stared_ratings = None
            ratings_fetch_timer = timer()
            next(ratings_fetch_timer)

            if fetch_ratings:
                rating_histogram_div = soup.find(
                    "span",
                    {
                        "class": "cr-widget-TitleRatingsAndHistogram",
                        "data-hook": "cr-widget-TitleRatingsAndHistogram",
                    },
                )

                if not isinstance(rating_histogram_div, bs4.Tag):
                    rating_histogram_div = soup.find(
                        "div", {"id": "cm_cr_dp_d_rating_histogram"}
                    )

                no_of_ratings_div = rating_histogram_div.find(
                    "div",
                    {
                        "class": "a-row a-spacing-medium averageStarRatingNumerical",
                    },
                )

                if isinstance(no_of_ratings_div, bs4.Tag):
                    no_of_ratings_span = no_of_ratings_div.find("span")
                    assert isinstance(
                        no_of_ratings_span, bs4.Tag
                    ), "Ratings Span Not Found"
                    no_of_ratings = int(
                        no_of_ratings_span.text.strip()
                        .replace('"', "")
                        .split()[0]
                        .replace(",", "")
                    )

                    table = rating_histogram_div.find_all("table")[-1]
                    assert isinstance(table, bs4.Tag), "Ratings Table Wasnt Found"

                    rows = table.find_all("tr")
                    individual_star_ratings = [
                        (
                            row.find_all("td")[0].text.strip(),
                            row.find_all("td")[2].text.strip(),
                        )
                        for row in rows
                    ]

                    def extract_stars(key):
                        result = re.search(r"\d+ star", key)
                        return result.group()

                    stared_ratings = {
                        f"no of {extract_stars(key)}": int(
                            (int(value[:-1]) / 100) * no_of_ratings
                        )
                        for key, value in individual_star_ratings
                    }
                else:
                    stared_ratings = {f"no of {key} star": 0 for key in range(1, 6)}
            ratings_fetch_timer = next(ratings_fetch_timer)

            # log success in fetching thing
            logging.info(f"fetched_everything [{product_id}]")

            return ProductInfo(
                new_phones_to_add,
                stared_ratings,
                data,
                data_func_timer,
                ratings_fetch_timer,
                other_phones_fetch_timer,
            )

        return _wrapper

    return inner_decorator


def get_all_products_data(link: str, function, headers: AmazonHeaders, **kwargs):
    """
    Fetches data for all products from the given Amazon search link.

    Args:
        link (str): The Amazon search link.
        function (function): The function to process the scraped data.
        headers (AmazonHeaders): The headers to be used for making requests.
        **kwargs: Additional keyword arguments to pass to the function.

    Returns:
        list[dict]: A list of product data dictionaries.
    """

    product_ids_to_scrape: set[str] = get_all_product_ids(link, headers, **kwargs)
    scraped_ids = []
    data = []

    code_timer = timer()
    next(code_timer)

    def fetch_webpage(url):
        response = requests.get(url, headers=headers.req)
        response.raise_for_status()
        return response.content

    while len(product_ids_to_scrape) > 0:
        id_to_scrape = product_ids_to_scrape.pop()
        logging.info(f"Scraping product with ID: {id_to_scrape}")

        if id_to_scrape in scraped_ids:
            continue

        link = f"https://www.amazon.in/dp/{id_to_scrape}"
        soup = bs4.BeautifulSoup(fetch_webpage(link), "lxml")
        output: ProductInfo = function(soup, id_to_scrape)

        if output is None:
            continue

        product_data = dict()
        product_data.update(output.data)

        if output.other_products is not None:
            product_ids_to_scrape.update(output.other_products)

        if output.ratings is not None:
            product_data.update(output.ratings)

        if product_data not in data:
            data.append(product_data)
            logging.info(f"product_scraped and saved [{id_to_scrape}]")
        else:
            logging.info(f"product data not new and so not saved [{id_to_scrape}]")

        logging.info(f"Remaining products to scrape: {len(product_ids_to_scrape)}")

    logging.info(f"DONE - TIME TAKEN: {next(code_timer)}")
    return data
