"""
Inspired by pdf.py in https://github.com/jgehrcke/github-repo-stats

If we ever need to wait for specific rendering aspects to happen, here is an
example for how to do that:

# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.expected_conditions import presence_of_element_located
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
import sys
import time

import selenium.common.exceptions
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.expected_conditions import presence_of_element_located


log = logging.getLogger()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(name)s %(levelname)s: %(message)s",
    datefmt="%y%m%d-%H:%M:%S",
)


# TODO We bumped this to capture Bokeh plot renderings which sometimes take a
# little while. It would however be better to dynamically respond to a render
# event (see module-level docstring).
SLEEP_BEFORE_SCREENSHOT_SECONDS = 10.0


CLI_ARGS = None

EXIT_CODE = 0


def main():
    global CLI_ARGS

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

    parser.add_argument(
        "--wait-for-canvas",
        action="store_true",
        help="Wait for <canvas> elem to pop up in DOM before taking screenshot",
    )

    args = parser.parse_args()
    CLI_ARGS = args

    url_to_open = args.url

    log.info("provided URL to open in browser: %s", url_to_open)
    png_path = os.path.join(args.outdir_path, args.filename_prefix + ".png")
    pdf_path = os.path.join(args.outdir_path, args.filename_prefix + ".pdf")

    screenshot(url_to_open, png_path)

    pdf_bytes = print_to_pdf(url_to_open)

    log.info("write %s bytes to %s", len(pdf_bytes), pdf_path)
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    log.info("done, exit with code %s", EXIT_CODE)
    sys.exit(EXIT_CODE)


def screenshot(url, pngpath):

    with _get_driver() as driver:

        driver.set_window_size(1700, 1900)
        log.info("driver.get(): %s", url)
        driver.get(url)
        _wait(driver)

        driver.get_screenshot_as_file(pngpath)
        log.info("Wrote file: %s", pngpath)


def print_to_pdf(url):

    with _get_driver() as driver:

        driver.set_window_size(1700, 1900)
        log.info("driver.get(): %s", url)
        driver.get(url)
        _wait(driver)

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


def _wait(driver):
    if not CLI_ARGS.wait_for_canvas:
        log.info("no waiter configured, default sleep")
        time.sleep(SLEEP_BEFORE_SCREENSHOT_SECONDS)
        return

    try:
        _wait_for_bokeh_canvas(driver)
    except selenium.common.exceptions.NoSuchElementException as exc:
        # log error and store non-zero exit code, but continue so that
        # we actually take the screenshot of the bad state.
        log.error("NoSuchElementException during _wait(): %s", exc)
        _set_exit_code(1)


def _wait_for_bokeh_canvas(driver):
    """
    May raise selenium.common.exceptions.NoSuchElementException upon timeout.

    Wait for Bokeh to add <canvas> elements to DOM. Use CSS selector syntax
    https://selenium-python.readthedocs.io/locating-elements.html#locating-elements-by-css-selectors
    https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Selectors

    Note: Bokeh uses multiple levels of so-called shadow roots. These can be
    thought of as virtual, independent DOM trees. That is, one cannot build a
    CSS selector path starting from the root of the outest DOM tree. It took a
    while to find a technique that allows for identifying shadow root objects,
    and then do sub-waits within those.
    """

    # First, set Selenium driver to the implicit wait mode which makes it so that
    # the `find_elements()` will wait until the given timeout.
    # https://selenium-python.readthedocs.io/waits.html#implicit-waits
    driver.implicitly_wait(10)

    # A div with CSS ID plot-history-0 is expected in the static HTML source.
    plotdiv = driver.find_element(By.CSS_SELECTOR, "div#plot-history-0")

    log.info("Found div#plot-history-0. Wait for Bokeh-generated div.bk-Column")
    # The actual DOM tree is expected to not have a div.bk-Column from the
    # start, i.e. right after loading the static HTML source that is not there.
    # When this pops up it means that the Bokeh Javascript has started
    # modifying the DOM. Once that elements pops up, it is expected to be the
    # so-called host of a shadow tree.
    shadow_host = plotdiv.find_element(By.CSS_SELECTOR, "div.bk-Column")

    # Extract the shadow tree object. This `shadow_root` attribute technique
    # only works from Chromium 96 onwards.
    shadow_root0 = shadow_host.shadow_root
    log.info("found shadow root below div.bk-Column")

    # In the highest-level shadow root we expect a div.bk-Figure to dynamically
    # pop up. Wait for that.
    div_figure = shadow_root0.find_element(By.CSS_SELECTOR, "div.bk-Figure")
    log.info("div.bk-Figure below shadow root 0 detected: %s", div_figure)

    # Another shadow root is expected, with div_figure being the host.
    shadow_root1 = div_figure.shadow_root
    div_canvas = shadow_root1.find_element(By.CSS_SELECTOR, "div.bk-Canvas")
    log.info("div.bk-Canvas below shadow root 1 detected: %s", div_canvas)

    # Another shadow root is expected, with div_canvas being the host.
    shadow_root2 = div_canvas.shadow_root
    canvas = shadow_root2.find_element(By.CSS_SELECTOR, "canvas.bk-layer")
    log.info("canvas.bk-layer below shadow root 2 detected: %s", canvas)


def _get_driver():
    wd_options = Options()
    wd_options.add_argument("--headless")
    wd_options.add_argument("--disable-gpu")
    wd_options.add_argument("--no-sandbox")
    wd_options.add_argument("--disable-dev-shm-usage")

    log.info("set up chromedriver with capabilities %s", wd_options.to_capabilities())

    driver = webdriver.Chrome(ChromeDriverManager().install(), options=wd_options)
    # The waiter is only optionally used later.
    # waiter = WebDriverWait(driver, 30)
    # Piggy-back waiter object on driver object, use a somewhat unique name
    # driver._waiter_bob = waiter

    log.info("webdriver is set up")
    return driver


def _set_exit_code(code: int):
    global EXIT_CODE
    EXIT_CODE = code


if __name__ == "__main__":
    main()
