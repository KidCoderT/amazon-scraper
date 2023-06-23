import re
import bs4
import time
import logging
from typing import Optional
from functools import wraps
from dataclasses import dataclass
import requests

logger = logging.getLogger()


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

    other_products: list[str] | None
    ratings: dict[str, int] | None
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


def get_all_product_ids(
    link: str,
    headers: AmazonHeaders,
    pages_to_scrape=10000000000000,
):
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

    i = 0

    try:
        while i < pages_to_scrape:
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
            logger.info(f"found page idx: {no_of_pages}")
            soup_pages.append(soup)
            i += 1

    except (TypeError, AttributeError):
        logger.warn(f"final_page: {page_link}")

    logger.info(f"full fetch duration: {time.monotonic() - start_time}")
    logger.info(f"scraped {no_of_pages} pages")
    logger.debug(f"avg page fetch time: {sum(fetch_times) / len(fetch_times)}")
    logger.debug(f"max page fetch time: {max(fetch_times)}")
    logger.debug(f"min page fetch time: {min(fetch_times)}")

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

    for soup in set(soup_pages):
        old_no = len(all_product_ids)
        scrape_soup_links(soup)
        logger.info(f"found {len(all_product_ids) - old_no} products")

    logger.info(f"full scrape duration: {next(scrape_timer)}")
    logger.info(f"scraped {len(all_product_ids)} product id's")
    logger.info(f"but only {len(set(all_product_ids))} product id's are unique")
    logger.debug(f"avg page half scrape time: {sum(scrape_times) / len(scrape_times)}")
    logger.debug(f"max page half scrape time: {max(scrape_times)}")
    logger.debug(f"min page half scrape time: {min(scrape_times)}")

    return set(all_product_ids)


def product_scraper(
    fetch_ratings: bool = True, get_others: bool = True, should_raise: bool = False
):
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
            logger.info("\nSCRAPING DATA FROM PRODUCT [%s] -------", product_id)

            data_func_timer = timer()
            next(data_func_timer)

            try:
                data = func(soup, product_id, *args, **kwargs)
                assert isinstance(data, dict), "Output Can Only Be A Dictionary"
                logger.info("STATUS: \033[31mSUCCESS\003[42m")
            except AssertionError as e:
                assert not should_raise, e
                logger.info("STATUS: \033[31mFAILED\003[39m")
                data = None

            data_func_timer = next(data_func_timer)
            logger.info("FUNC SCRAPER TOOK: [%s]", data_func_timer)

            if data is None:
                return None

            # Scraping New Phones
            new_phones_to_add = [] if get_others else None
            other_phones_fetch_timer = timer()
            next(other_phones_fetch_timer)

            if get_others and isinstance(new_phones_to_add, list):
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

            # Scraping Ratings
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
                    {"class": "a-row a-spacing-medium averageStarRatingNumerical"},
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
            logger.info(
                "TOOLKIT SCRAPER TOOK: [%s]",
                ratings_fetch_timer + other_phones_fetch_timer,
            )

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


def get_all_products_data(
    link: str,
    function,
    headers: AmazonHeaders,
    pages_to_scrape=10000000000000,
    max_products=float("inf"),
):
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

    product_ids_to_scrape: set[str] = get_all_product_ids(
        link, headers, pages_to_scrape
    )
    scraped_ids = []
    data = []

    code_timer = timer()
    next(code_timer)

    def fetch_webpage(url):
        response = requests.get(url, headers=headers.req)
        response.raise_for_status()
        return response.content

    while len(product_ids_to_scrape) > 0 and len(scraped_ids) < max_products:
        id_to_scrape = product_ids_to_scrape.pop()
        logger.info(f"Scraping product with ID: {id_to_scrape}")

        if id_to_scrape in scraped_ids:
            continue

        try:
            link = f"https://www.amazon.in/dp/{id_to_scrape}"
            soup = bs4.BeautifulSoup(fetch_webpage(link), "lxml")
            output: Optional[ProductInfo] = function(soup, id_to_scrape)
        except:
            continue

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
            logger.info(f"ADDED?: YES")
        else:
            logger.info(f"ADDED?: NO")

        logger.info(f"REMAINING: {len(product_ids_to_scrape)}")
        logger.info(f"SCRAPED: {len(data)}")
        logger.info("-------")

    logger.info(f"DONE - TIME TAKEN: {next(code_timer)}")
    return data
