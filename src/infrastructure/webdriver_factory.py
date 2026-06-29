import os
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from src.config import TIMEOUT

logger = logging.getLogger(__name__)


def _locate_chromium_binary() -> str | None:
    """Return the path of the chromium/chrome binary, or None."""
    candidates = [
        "/usr/sbin/chromium-browser",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    # Last resort — check PATH
    import shutil
    return shutil.which("chromium-browser") or shutil.which("chromium") or shutil.which("google-chrome")


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
            # Local development — set the binary location if found
            binary = _locate_chromium_binary()
            if binary:
                options.binary_location = binary

            # Try Selenium's built-in Manager first, fall back to webdriver-manager
            driver = WebDriverFactory._create_driver_with_fallback(options)

        # Further mask automation fingerprints
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
        )

        wait = WebDriverWait(driver, TIMEOUT)
        return driver, wait

    @staticmethod
    def _create_driver_with_fallback(options: Options):
        """
        Attempt to create a Chrome driver using several strategies:
          1. webdriver-manager Python package (fast, handles custom Chromium builds).
          2. Selenium's built-in Selenium Manager (Selenium 4.6+).
          3. Direct chromedriver lookup on PATH or common locations.
        """
        # --- Strategy 1: webdriver-manager package ---
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            from webdriver_manager.core.os_manager import ChromeType

            # Pick CHROMIUM if the binary path contains "chromium", else GOOGLE
            chrome_type = ChromeType.CHROMIUM if (
                options.binary_location and "chromium" in options.binary_location
            ) else ChromeType.GOOGLE

            driver_path = ChromeDriverManager(chrome_type=chrome_type).install()
            service = Service(executable_path=driver_path)
            return webdriver.Chrome(service=service, options=options)
        except ImportError:
            logger.debug("webdriver-manager package not installed")
        except Exception as exc:
            logger.debug("webdriver-manager failed: %s", exc)

        # --- Strategy 2: Selenium's built-in Manager ---
        try:
            return webdriver.Chrome(options=options)
        except Exception as exc:
            logger.debug("Selenium Manager failed: %s", exc)

        # --- Strategy 3: Look for chromedriver on PATH ---
        import shutil
        driver_path = shutil.which("chromedriver")
        if driver_path:
            return webdriver.Chrome(service=Service(executable_path=driver_path), options=options)

        # --- All strategies exhausted ---
        raise RuntimeError(
            "Unable to obtain ChromeDriver. Try one of:\n"
            "  1. sudo dnf install chromedriver\n"
            "  2. Set CHROMEDRIVER_BIN=/path/to/chromedriver in .env\n"
            "  3. Ensure webdriver-manager is installed: uv add webdriver-manager"
        )