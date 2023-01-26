"""
Inspired by pdf.py in https://github.com/jgehrcke/github-repo-stats

If we ever need to wait for specific rendering aspects to happen, here is an
example for how to do that:

# Wait for Vega to add <svg> elemtn(s) to DOM.
#
# waiter = WebDriverWait(driver, 10)
# first_svg = waiter.until(
#     presence_of_element_located((By.CSS_SELECTOR, "div>svg"))
# )
# log.info("first <svg> element detected: %s", first_svg)

The `time.sleep(0.5)` in each driver context is there to make it more likely
that rendering completed before generating PDF and PNG. It's unclear if this is
actually needed. A matter of caution with practically no downside right now.
"""

import argparse
import base64
import json
import logging
import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.expected_conditions import presence_of_element_located


log = logging.getLogger()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s: %(message)s",
    datefmt="%y%m%d-%H:%M:%S",
)


# TODO We bumped this to capture Bokeh plot renderings which sometimes take a
# little while. It would however be better to dynamically respond to a render
# event (see module-level docstring).
SLEEP_BEFORE_SCREENSHOT_SECONDS = 10.0


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "url",
        metavar="URL",
    )

    parser.add_argument(
        "outdir_path",
        metavar="OUTPUT_DIR_PATH",
    )

    parser.add_argument(
        "filename_prefix",
        metavar="FILENAME_PREFIX",
    )

    args = parser.parse_args()

    url_to_open = args.url

    log.info("provided URL to open in browser: %s", url_to_open)
    png_path = os.path.join(args.outdir_path, args.filename_prefix + ".png")
    pdf_path = os.path.join(args.outdir_path, args.filename_prefix + ".pdf")

    screenshot(url_to_open, png_path)

    pdf_bytes = print_to_pdf(url_to_open)

    log.info("write %s bytes to %s", len(pdf_bytes), pdf_path)
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    log.info("done")


def screenshot(url, pngpath):

    with _get_driver() as driver:

        driver.set_window_size(1700, 1900)
        driver.get(url)

        time.sleep(SLEEP_BEFORE_SCREENSHOT_SECONDS)
        driver.get_screenshot_as_file(pngpath)
        log.info("Wrote file: %s", pngpath)


def print_to_pdf(url):

    with _get_driver() as driver:

        driver.set_window_size(1700, 1900)
        driver.get(url)

        time.sleep(SLEEP_BEFORE_SCREENSHOT_SECONDS)

        b64_text = send_print_request(driver)
        log.info("decode b64 doc (length: %s chars) into bytes", len(b64_text))
        return base64.b64decode(b64_text)


def send_print_request(driver):
    # Construct chrome dev tools print request.
    # https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-printToPDF
    # Also see https://bugs.chromium.org/p/chromium/issues/detail?id=603559 for
    # context.
    print_options = {
        "scale": 0.7,
        "paperWidth": 16,  # inches
        "paperHeight": 12,  # inches
        "martinTop": 5,
        "martinBottom": 0,
        "martinLeft": 0,
        "martinRight": 0,
        "displayHeaderFooter": False,
        "printBackground": False,
    }

    url = (
        driver.command_executor._url
        + f"/session/{driver.session_id}/chromium/send_command_and_get_result"
    )

    log.info("send Page.printToPDF webdriver request to %s", url)

    response = driver.command_executor._request(
        "POST", url, json.dumps({"cmd": "Page.printToPDF", "params": print_options})
    )

    if "value" in response:
        if "data" in response["value"]:
            log.info("got expected Page.printToPDF() response format")
            return response["value"]["data"]

    log.error("unexpected response: %s", response)
    raise Exception("unexpected webdriver response")


def _get_driver():
    wd_options = Options()
    wd_options.add_argument("--headless")
    wd_options.add_argument("--disable-gpu")
    wd_options.add_argument("--no-sandbox")
    wd_options.add_argument("--disable-dev-shm-usage")

    log.info("set up chromedriver with capabilities %s", wd_options.to_capabilities())

    d = webdriver.Chrome(ChromeDriverManager().install(), options=wd_options)

    log.info("webdriver is set up")
    return d


if __name__ == "__main__":
    main()
