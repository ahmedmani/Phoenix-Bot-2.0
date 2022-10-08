from selenium.webdriver import DesiredCapabilities
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait
# from utils import create_msg
import random, re, requests, string, threading



class AnyEc:
    """Use with WebDriverWait to combine expected_conditions
    in an OR.
    """

    def no_amazon_image(self):
        prefs = {"profile.managed_default_content_settings.images": 2}
        options.add_experimental_option("prefs", prefs)
    
    
    def yes_amazon_image(self):
        prefs = {"profile.managed_default_content_settings.images": 0}
        options.add_experimental_option("prefs", prefs)
    
    
    def wait_for_element(self, d, e_id, time=30):
        """
        Uses webdriver(d) to wait for page title(title) to become visible
        """
        return WebDriverWait(d, time).until(ec.presence_of_element_located((By.ID, e_id)))
    
    
    def wait_for_element_by_xpath(self, d, e_path, time=30):
        return WebDriverWait(d, time).until(
            ec.presence_of_element_located((By.XPATH, e_path))
        )
    
    
    def wait_for_element_by_class(self, d, e_class, time=30):
        """
        Uses webdriver(d) to wait for page title(title) to become visible
        """
        return WebDriverWait(d, time).until(
            ec.presence_of_element_located((By.CLASS_NAME, e_class))
        )
    
    
    def wait_for_title(self, d, title, path):
        """
        Uses webdriver(d) to navigate to get(path) until it equals title(title)
        """
        while d.title != title:
            d.get(path)
            WebDriverWait(d, 1000)
    
    
    def wait_for_page(self, d, title, time=30):
        """
        Uses webdriver(d) to wait for page title(title) to become visible
        """
        WebDriverWait(d, time).until(ec.title_is(title))
    
    
    def wait_for_either_title(self, d, title1, title2, time=30):
        """
        Uses webdriver(d) to wait for page title(title1 or title2) to become visible
        """
        try:
            WebDriverWait(d, time).until(AnyEc(ec.title_is(title1), ec.title_is(title2)))
        except Exception:
            pass


    def wait_for_any_title(self, d, titles, time=30):
        """
        Uses webdriver(d) to wait for page title(any in the list of titles) to become visible
        """
        WebDriverWait(d, time).until(AnyEc(*[ec.title_is(title) for title in titles]))


    def button_click_using_xpath(self, d, xpath):
        """
        Uses webdriver(d) to click a button using an XPath(xpath)
        """
        button_menu = WebDriverWait(d, 10).until(
            ec.element_to_be_clickable((By.XPATH, xpath))
        )
        action = ActionChains(d)
        action.move_to_element(button_menu).pause(1).click().perform()


    def field_send_keys(self, d, field, keys):
        """
        Uses webdriver(d) to fiend a field(field), clears it and sends keys(keys)
        """
        elem = d.find_element_by_name(field)
        elem.clear()
        elem.send_keys(keys)


    def has_class(self, element, class_name):
        classes = element.get_attribute("class")

        return class_name in classes
    
    
    def add_cookies_to_session_from_driver(self, driver, session):
        cookies = driver.get_cookies()

        [
            session.cookies.set_cookie(
                requests.cookies.create_cookie(
                    domain=cookie["domain"],
                    name=cookie["name"],
                    value=cookie["value"],
                )
            )
            for cookie in cookies
        ]
    
    
    def enable_headless(self):
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
    
        return options
    
    
    def change_driver(self, status_signal, loc):
        fin = open(loc, 'rb')
        data = fin.read()
        val = "$" + "".join(random.choices(string.ascii_lowercase, k=3)) + "_" + \
              "".join(random.choices(string.ascii_letters + string.digits, k=22)) + "_"
        result = re.search(b"[$][a-z]{3}_[a-zA-Z0-9]{22}_", data)
        if result is not None:
            try:
                status_signal.emit(create_msg("Changing value in Chromedriver", "normal"))
                data = data.replace(result.group(0), val.encode())
                fin.close()
                fin = open(loc, 'wb')
                fin.truncate()
                fin.write(data)
                fin.close()
            except:
                status_signal.emit(create_msg("Error modifying chromedriver", "error"))
        else:
            fin.close()
    
    
    def open_browser(self, link, cookies):
        threading.Thread(target=start_browser, args=(link, cookies)).start()
    
    
    def start_browser(self, link, cookies):
        caps = DesiredCapabilities().CHROME
        caps["pageLoadStrategy"] = "eager"
        chrome_options = ChromeOptions()
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        driver = Chrome(desired_capabilities=caps, executable_path=driver_path, options=chrome_options)
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
            Object.defineProperty(window, 'navigator', {
                value: new Proxy(navigator, {
                  has: (target, key) => (key === 'webdriver' ? false : key in target),
                  get: (target, key) =>
                    key === 'webdriver'
                      ? undefined
                      : typeof target[key] === 'function'
                      ? target[key].bind(target)
                      : target[key]
                })
            })
                      """
            },
        )
        driver.get(link)
        for cookie in cookies:
            driver.add_cookie({
                "name": cookie["name"],
                "value": cookie["value"],
                "domain": cookie["domain"]
            })
        driver.get(link)
