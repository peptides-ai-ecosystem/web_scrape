import time
from selenium.webdriver.support import expected_conditions as EC
from src.core.interfaces import IExtractor

class BaseExtractor(IExtractor):
    def get_text(self, driver, element):
        """Read an element's text via JS ``innerText``.

        Selenium's ``.text`` (ChromeDriver getElementText) returns ``""`` for
        elements whose computed opacity is 0 — e.g. pep-pedia's below-fold
        ``reveal-on-scroll`` sections (CSS scroll-driven animation). ``innerText``
        still returns the real text, so this fixes those reads.

        SVG elements have no ``innerText`` (``SVGElement`` doesn't inherit
        ``HTMLElement``), so fall back to ``textContent`` for them.
        """
        try:
            return driver.execute_script(
                "var t = arguments[0].innerText;"
                "return (t === undefined || t === null) ? arguments[0].textContent : t;",
                element,
            )
        except Exception:
            return element.text

    def safe_click(self, driver, wait, element):
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
            wait.until(EC.element_to_be_clickable(element)).click()
        except:
            driver.execute_script("arguments[0].click();", element)
    
    def wait_for_loading(self, seconds=0.3):
        time.sleep(seconds)
