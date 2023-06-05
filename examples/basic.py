import json
import logging
import src

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,  # Set the logging level (e.g., INFO, DEBUG, WARNING)
        format="%(asctime)s [%(levelname)s] %(message)s",  # Set the log message format
        datefmt="%Y-%m-%d %H:%M:%S",  # Set the date/time format
    )

    headers = src.AmazonHeaders(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "en-US",
    )

    @src.product_scraper(get_others=True)
    def test(soup, id):
        # Make my scraper
        return {}

    with open("data.json", "w") as file:
        data = src.get_all_products_data(
            "https://www.amazon.in/s?rh=n%3A1805560031&fs=true&ref=lp_1805560031_sar",
            test,
            headers,
            max_products=10,
        )
        json.dump(data, file, indent=4)
