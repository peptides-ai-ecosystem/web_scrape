import time
from selenium.webdriver.support import expected_conditions as EC
from src.core.interfaces import IExtractor

class BaseExtractor(IExtractor):
    def safe_click(self, driver, wait, element):
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
            wait.until(EC.element_to_be_clickable(element)).click()
        except:
            driver.execute_script("arguments[0].click();", element)
    
    def wait_for_loading(self, seconds=0.3):
        time.sleep(seconds)
