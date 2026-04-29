import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from ..config import TIMEOUT


class WebDriverFactory:
    @staticmethod
    def create_driver():
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--disable-extensions")
        options.add_argument("--no-zygote")
        options.add_argument("--window-size=1920,1080")

        # Spoof a real browser user-agent — many sites block headless Chrome
        options.add_argument(
            "--user-agent=Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/147.0.0.0 Safari/537.36"
        )

        # Hide headless signals that sites use to detect and block bots
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        chromedriver_bin = os.environ.get("CHROMEDRIVER_BIN")
        chrome_bin = os.environ.get("CHROME_BIN")

        if chromedriver_bin and os.path.isfile(chromedriver_bin):
            # Docker / server environment (or when explicit paths are provided)
            if chrome_bin:
                options.binary_location = chrome_bin
            service = Service(executable_path=chromedriver_bin)
            driver = webdriver.Chrome(service=service, options=options)
        else:
            # Local development: let Selenium's built-in Manager handle it (Selenium 4.6+)
            # We explicitly set binary_location if it's in a non-standard path like /usr/sbin/
            if os.path.isfile("/usr/sbin/chromium-browser"):
                options.binary_location = "/usr/sbin/chromium-browser"
            elif os.path.isfile("/usr/bin/chromium-browser"):
                options.binary_location = "/usr/bin/chromium-browser"
            
            # Using no Service() object triggers Selenium Manager automatically
            driver = webdriver.Chrome(options=options)

        # Further mask automation fingerprints
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
        )

        wait = WebDriverWait(driver, TIMEOUT)
        return driver, wait