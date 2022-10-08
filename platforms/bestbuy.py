import undetected_chromedriver as webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import urllib3, requests, time, json, sys, re, random, string, os, code, secrets, email, imaplib
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.ssl_ import create_urllib3_context
from server.src.utils.exceptions import Authexp, Internalexp
from bs4 import BeautifulSoup
from server.src.utils.selenium_utils import AnyEc



from supabase import create_client, Client
url: str = 
key: str = 
supabase: Client = create_client(url, key)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


CIPHERS = ('DEFAULT:@SECLEVEL=2')
class CipherAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context(ciphers=CIPHERS)
        kwargs['ssl_context'] = context
        return super(CipherAdapter, self).init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        context = create_urllib3_context(ciphers=CIPHERS)
        kwargs['ssl_context'] = context
        return super(CipherAdapter, self).proxy_manager_for(*args, **kwargs)

def parse(text):
    try:
        data = json.loads(text)
    except:
        return False
    else:
        return data


class BestBuy:


    def __init__(self, stat, profile, product, supabase, userid):
        self.session = requests.Session()
        # self.session.proxies = {"https": "https://localhost:8080"}
        # self.session.verify = False
        self.status_signal = stat
        self.supabase = supabase
        self.userid = userid
        self.session.mount('https://www.bestbuy.com/', CipherAdapter())
        self.header = {'accept': 'application/json, text/javascript, */*; q=0.01', 'accept-encoding': 'gzip, deflate, br', 'accept-language': 'en-US,en;q=0.9,fr;q=0.8,ar;q=0.7', 'cache-control': 'no-cache', 'content-type': 'application/json', 'dnt': '1', 'pragma': 'no-cache', 'referer': 'https://www.bestbuy.com/', 'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="98", "Google Chrome";v="98"', 'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"', 'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-origin', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36'}
        self.selem_utils = AnyEc()
        self.profile = profile
        self.cookies = {}#filled in the login function
        self.ccid = "" #filled in the checkout function
        self.product = product
        self.skuid = self.product.split("skuId")[1].replace("=", "")
        self.status_signal.emit({'msg': "Starting", "status": "normal"})
        
    

    def get_cart(self):
        r = self.session.get("https://www.bestbuy.com/cart/json", headers=self.header)
        try:
            data = json.loads(r.text)
        except:
            self.status_signal.emit({"msg": "error fetching cart", "status": "normal"})
        else:
            return data["cart"]["lineItems"]    

    def clear_cart(self):
        lineitems = self.get_cart()
        self.status_signal.emit({"msg": "clearing cart", "status": "normal"})
        print(lineitems)
        if lineitems:
            for i in lineitems:
                r = self.session.delete("https://www.bestbuy.com/cart/item/" + i["id"], headers=self.header)
            if parse(r.text)["order"]["cartItemCount"] == "0":
                return
            else:
                self.status_signal.emit({"msg": "error clearing cart", "status": "error"})

    def atc(self, skuid):
        b = {"items":[{"skuId": skuid}]}
        r = self.session.post("https://www.bestbuy.com/cart/api/v1/addToCart", json=b, headers=self.header)     
        data = parse(r.text)
        if data["cartCount"] == 1:
            self.status_signal.emit({"msg": "item added to cart", "status": "normal"})
            # for i in data["summaryItems"]:
                # if skuid == i["skuId"]:
                    # self.itemid =  i["lineId"]
            return
        else:
            self.status_signal.emit({"msg": "error adding item cart", "status": "normal"})

    def check_stock(self, skuid):
        self.status_signal.emit({"msg": "Checking stock", "status": "normal"})
        url = "https://www.bestbuy.com/api/tcfb/model.json?paths=%5B%5B%22shop%22%2C%22scds%22%2C%22v2%22%2C%22page%22%2C%22tenants%22%2C%22bbypres%22%2C%22pages%22%2C%22globalnavigationv5sv%22%2C%22header%22%5D%2C%5B%22shop%22%2C%22buttonstate%22%2C%22v5%22%2C%22item%22%2C%22skus%22%2C{}%2C%22conditions%22%2C%22NONE%22%2C%22destinationZipCode%22%2C%22%2520%22%2C%22storeId%22%2C%22%2520%22%2C%22context%22%2C%22cyp%22%2C%22addAll%22%2C%22false%22%5D%5D&method=get".format(skuid)
        r = self.session.get(url, headers=self.header)
        try:
            item = re.findall(r'{"buttonStateResponseInfos":\[(.*?)\]}', r.text)[0]
            
            data = json.loads(item)
            if data["skuId"] == skuid and data["buttonState"] in ["ADD_TO_CART","PRE_ORDER"]:
                self.status_signal.emit({"msg": "item in stock, proceeding to checkout", "status": "normal"})
                return True
            else:
                self.status_signal.emit({"msg": "item not in stock, sleeping", "status": "normal"})
                return False
        except Exception as ex:
            self.status_signal.emit({"msg": "error parsing json: " + str(ex), "status": "error"})

    def add_card(self, driver=False):
        self.status_signal.emit({'msg': "adding card", "status": "normal"})
        if not driver: 
            driver = webdriver.Chrome()
            driver.get("https://www.bestbuy.com")

            for c, j in self.session.cookies.get_dict().items():
                try:
                    driver.add_cookie({"name": c.strip(), "value": j})
                except:
                    print("not added")
        while True:
            driver.get("https://www.bestbuy.com/profile/c/billinginfo/cc/add")
            try:
                self.selem_utils.wait_for_element_by_xpath(driver, '//*[@id="credit-cards"]/div/div/div/div[2]/h1')
            except:
                self.status_signal.emit({'msg': "error adding card", "status": "normal"})    
                if self.debug:       
                    code.interact(local=locals()) 

            self.selem_utils.wait_for_element_by_xpath(driver, '//*[@id="cardNumber-id"]').send_keys(self.profile["ccnum"])
            time.sleep(1)
            try:
                driver.find_elements(By.XPATH, '//*[@id="expirationMonth-dropdown-input"]')[0].send_keys(self.profile["expm"])
            except:
                self.status_signal.emit({'msg': "invalid card number", "status": "error"})
            driver.find_elements(By.XPATH, '//*[@id="expirationYear-dropdown-input"]')[0].send_keys(self.profile["expy"])
            driver.find_elements(By.XPATH, '//*[@id="firstName-id"]')[0].send_keys(self.profile["name"])
            driver.find_elements(By.XPATH, '//*[@id="lastName-id"]')[0].send_keys(self.profile["lname"])
            driver.find_elements(By.XPATH, '//*[@id="addressLine1-id"]')[0].send_keys(self.profile["adr1"])
            driver.find_elements(By.XPATH, '//*[@id="addressLine2-id"]')[0].send_keys(self.profile["adr2"])
            driver.find_elements(By.XPATH, '//*[@id="city-id"]')[0].send_keys(self.profile["city"])
            driver.find_elements(By.XPATH, '//*[@id="state-dropdown-input"]')[0].send_keys(self.profile["state"])
            driver.find_elements(By.XPATH, '//*[@id="zip-id"]')[0].send_keys(self.profile["zipcode"])
            driver.find_elements(By.XPATH, '//*[@id="phone-id"]')[0].send_keys(self.profile["phone"])
            try:
                driver.find_elements(By.XPATH, '//*[@id="credit-cards"]/div/div/div/form/div[5]/button')[0].click()
            except:
                driver.find_elements(By.XPATH, '//*[@id="credit-cards"]/div/div/div/form/div[7]/button')[0].click()
            time.sleep(3)
            try:
                driver.find_elements(By.XPATH, '//*[@id="credit-cards"]/div/div/div/div[4]/div[2]/button[1]')[0].click()
            except:
                pass
            else:
                time.sleep(1)
            try:
                err = driver.find_elements(By.XPATH, '//*[@id="credit-cards"]/div/div/div/div[3]/div[1]/div')[0].text
                if "your new card has been successfully" not in err.lower():
                    print("card was not added")
                    self.status_signal.emit({'msg': "error adding card error code: x16", "status": "error"})
                    raise Exception()
            except: #either element not found or card not added
                self.status_signal.emit({'msg': "error adding card, trying again", "status": "error"})
                time.sleep(2)
                continue
                # try:
                #     err = driver.find_elements(By.XPATH, '//*[@id="credit-cards"]/div/div/div/div[3]/div')[0].text


            else:
                self.status_signal.emit({'msg': "card added", "status": "normal"})
                break
        self.update_cookies(driver.get_cookies())
        driver.quit()

    def update_location(self):
        self.status_signal.emit({'msg': "updating location", "status": "normal"})
        r = self.session.get("https://www.bestbuy.com/site/store-locator", headers=self.header)
        uuid = re.findall(r'"uuid":"(.*?)",', r.text)[0]
        header = {'accept': '*/*', 'accept-encoding': 'gzip, deflate, br', 'accept-language': 'en-US,en;q=0.9,fr;q=0.8,ar;q=0.7', 'cache-control': 'no-cache', 'dnt': '1', 'pragma': 'no-cache', 'referer': 'https://www.bestbuy.com/site/store-locator', 'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="99", "Google Chrome";v="99"', 'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"', 'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-origin', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36'}
        r = self.session.get("https://www.bestbuy.com/api/tcfb/model.json?paths=%5B%5B%22shop%22%2C%22stores%22%2C%22location%22%2C%22v1%22%2C%22us%22%2C%22store%22%2C%22byZipcode%22%2C%22optional%22%2C%22zipcodes%22%2C%22{}%22%2C%22options%22%2C%5B%22types%3DStore%26storeTypes%3DBigBox%2CPacStandaloneStore%2COutletCenter%26status%3DOpen%26miles%3D250%22%2C%22types%3DWarehouse%26facilityTypes%3DApplianceWarehouse%26status%3DOpen%26hasPickup%3Dtrue%26isPhysicalWarehouse%3Dfalse%26miles%3D250%22%2C%22types%3DWarehouse%26facilityTypes%3DCrossdock%2CDeliveryPadWarehouse%26status%3DOpen%26hasPickup%3Dtrue%26isPhysicalWarehouse%3Dfalse%26miles%3D250%22%5D%2C%22storeData%22%2C%7B%22from%22%3A0%2C%22to%22%3A14%7D%2C%5B%22distance%22%2C%22geoCoordinate%22%2C%22id%22%5D%5D%5D&method=get".format(self.profile["zipcode"]), headers=self.header)
        stores = re.findall(r'"types=Store&storeTypes=BigBox,PacStandaloneStore,OutletCenter&status=Open&miles=250":{"storeData":(.*?)},"types', r.text)[0]
        data = json.loads(stores)
        r = self.session.post("https://www.bestbuy.com/profile/rest/preferred/locations/{}/store/{}".format(uuid, data["0"]["id"]["value"]), headers=self.header)
        
        if int(parse(r.text)["storeId"]) == data["0"]["id"]["value"]:
            self.store_id = data["0"]["id"]["value"]
            self.status_signal.emit({'msg': "location updated", "status": "normal"})
        else:
            self.status_signal.emit({'msg': "error updating location", "status": "error"})
            if self.debug:
                code.interact(local=dict(globals(), **locals())) 

    def add_address(self):
        self.status_signal.emit({'msg': "adding shipping address", "status": "normal"})

        b = {
           "firstName": self.profile["name"],
           "middleName": self.profile["mname"],
           "lastName": self.profile["lname"],
           "addressLine1": self.profile["adr1"],
           "addressLine2": self.profile["adr2"],
           "city": self.profile["city"],
           "state": self.profile["state"],
           "postalCode": self.profile["zipcode"],
           "country": self.profile["country"].lower(),
           "phone": self.profile["phone"],
           "phoneNumber": self.profile["phone"],
           "userOverridden":True,
           "primary":True
        }

        r = self.session.post("https://www.bestbuy.com/profile/rest/c/address/shipping/create", headers=self.header, json=b)           
        data = parse(r.text)
        if data:
            self.status_signal.emit({'msg': "shipping address added", "status": "normal"})
            self.adr_id = data["id"]
        else:
            self.status_signal.emit({'msg': "error adding shipping address", "status": "error"})

    def login(self, driver=False):
        if not driver:
            driver = webdriver.Chrome()
        self.status_signal.emit({'msg': "Logging in", "status": "normal"})
        j = 0 
        while True:
            driver.get("https://www.bestbuy.com/identity/global/signin")
            try:
                self.selem_utils.wait_for_element(driver, "fld-e").send_keys(self.profile["email"])
            except:#??
                input("error logging in could not find login email")
                if self.debug:
                    code.interact(local=dict(globals(), **locals())) 
            else:
                self.selem_utils.wait_for_element(driver, "fld-p1").send_keys(self.profile["password"])    
                driver.find_elements(By.XPATH, "//button[contains(@class,'cia-form__controls__submit')]")[0].click()
            
            time.sleep(5)      
            
            try:#checking for errors
                err = driver.find_elements(By.XPATH, '/html/body/div[1]/div/section/main/div[2]/div[1]/div/div/div/div[1]/div/strong/div')[0].text            
            except:
                pass
            else:
                if "didn't find an account with that email address" in err:
                    if j == 2: #used to make sure bestbuy is not rejecting our login and password is indeed incorrect
                        # raise Authexp({"message": "wrong email"})   
                        pass   
                    j += 1
                elif "password was incorrect" in err:
                    if j == 2:
                        # raise Authexp({"message": "wrong password"})
                        pass      
                    j += 1
                elif "The email or password did not match our records" in err:
                    pass
                else:#unexpected error
                    print(err)
                    if self.debug:
                        code.interact(local=dict(globals(), **locals())) 

            try:#try to see if we are in login verification page or not
                driver.find_elements(By.XPATH, '//*[@id="verificationCode"]')[0]
            except:
                try:
                    driver.find_elements(By.XPATH, '//*[@id="email-radio"]')[0]
                except:
                    pass
                else:
                    self.verify_login_request(driver)
            else:
                self.verify_login_request(driver)

            # self.selem_utils.wait_for_title(driver, 'Account Home - Best Buy', "https://www.bestbuy.com/site/customer/myaccount")
            while driver.title != 'Account Home - Best Buy':
                driver.get("https://www.bestbuy.com/site/customer/myaccount")
                try:
                    driver.find_elements(By.ID, 'fld-e')[0]
                except: #we are making sure we load the myacount page if we are logged in (to fix a bug) we also checking that login was succes if email field found break and relogin
                    pass
                else:
                    break 
                
    
            if "Welcome back" in driver.page_source:
                self.status_signal.emit({'msg': "Login successful", "status": "normal"})
                self.cookies = driver.get_cookies()
                self.update_cookies(driver.get_cookies())
                return driver
            else:
                self.status_signal.emit({'msg': "Login not successful!!", "status": "normal"})

    def verify_login_request(self, driver):
        self.status_signal.emit({'msg': "verifying login request", "status": "normal"})

        try:
            driver.find_elements(By.XPATH, '//*[@id="email-radio"]')[0].click()
            driver.find_elements(By.XPATH, '/html/body/div[1]/div/section/main/div[2]/div[1]/div/div/div/div/div/form/div/button')[0].click()
            k = 0
        except Exception as ex:
            pass
        try:
            lcode = ""
            while True:
                vcode = self.fetch_code()
                if (lcode != vcode) and (vcode):
                    self.status_signal.emit({'msg': "code received", "status": "normal"})
                    x = self.selem_utils.wait_for_element_by_xpath(driver, '//*[@id="verificationCode"]')
                    x.send_keys(Keys.CONTROL + "a")
                    x.send_keys(Keys.DELETE)
                    x.send_keys(vcode)
                    driver.find_elements(By.XPATH, '/html/body/div[1]/div/section/main/div[2]/div[1]/div/div/div/div/div/form/div[2]/button')[0].click()
                    try:
                        time.sleep(2)
                        err = driver.find_elements(By.XPATH, '/html/body/div[1]/div/section/main/div[2]/div[1]/div/div/div/div[1]/div')[0]
                        if "entered may be incorrect or expired" not in err:
                            break
                        else:
                            time.sleep(20)
                    except:
                        try:
                            driver.find_elements(By.XPATH, '//*[@id="fld-p1"]')[0]
                        except:
                            pass
                        else:
                            break
                else:
                    print("vcode", vcode)
                    print("lcode", lcode)
                    time.sleep(20)
                lcode = vcode
        except Exception as ex:
            print(ex)
            self.status_signal.emit({'msg': "error typing code no input text found", "status": "error"})
        else:
            # driver.find_elements(By.XPATH, '/html/body/div[1]/div/section/main/div[2]/div[1]/div/div/div/div/div/form/div[2]/button')[0].click()
            driver.find_elements(By.XPATH, '//*[@id="fld-p1"]')[0].send_keys(self.profile["password"])
            driver.find_elements(By.XPATH, '//*[@id="reenterPassword"]')[0].send_keys(self.profile["password"])
            driver.find_elements(By.XPATH, '/html/body/div[1]/div/section/main/div[2]/div[1]/div/div/div/div/div/form/div[4]/button')[0].click()
            time.sleep(3)

    def create_bb(self):
        def phn():
            n = '0000000000'
            while '9' in n[3:6] or n[3:6]=='000' or n[6]==n[7]==n[8]==n[9]:
                n = str(random.randint(10**9, 10**10-1))
            return n[:3]  + n[3:6] + n[6:]
        driver = webdriver.Chrome()
        while True:
            driver.get("https://www.bestbuy.com/identity/global/createAccount")
            
            try:
                self.selem_utils.wait_for_page(driver, 'Best Buy: Create an Account')
            except:
                self.status_signal.emit({'msg': "error loading account page", "status": "normal"})
                if self.debug:
                    code.interact(local=locals())
            alias = ['Elias Lynn', 'Kira Everett', 'Mariela Booker', 'Avery Michael', 'Samuel Cabrera', 'Kamden Cross', 'Craig Olson', 'Matthias Curry', 'Joey Mercer', 'Jeremy Howell', 'Jayvon Mccall', 'Hezekiah Cobb', 'Harley Deleon', 'Abbie Heath', 'Jayla Aguirre', 'Cheyenne Mendoza', 'Kadyn Douglas', 'Jaeden Burns', 'Amy Reid', 'Franco Mcconnell', 'Payton Hughes', 'Presley Christian', 'Kai Ferguson', 'Kailey Gordon', 'Cornelius Mcgee', 'Noah Lara', 'Abram Rios', 'Alisha Schmitt', 'Caitlin Rollins', 'Helena Love', 'Jaidyn Richard', 'Madalyn Ochoa', 'Jakayla Donovan', 'Carmelo Mccall', 'Gerardo Higgins', 'August Gibson', 'Chaim Calhoun', 'Karissa Medina', 'Haleigh Guzman', 'Zachariah Horne', 'Tanya Li', 'Marlene Webb', 'Junior Bonilla', 'Shelby Lucas', 'Atticus Shannon', 'Yahir Cuevas', 'Alayna Merritt', 'Caiden Mcintosh', 'Santos Roberson', 'Noemi Henderson', 'Tommy Rice', 'Brodie Huffman', 'Patricia Dickson', 'Graham Jacobs', 'Fiona Browning', 'Camilla Chapman', 'Jace Campbell', 'Makenna Aguilar', 'Abdiel Sheppard', 'Janet Robinson', 'Kiera Gardner', 'Skyla Roth', 'Savanah Gamble', 'Kadin Villegas', 'German Robertson', 'Maurice Parrish', 'Jayden Christian', 'Justice Howell', 'Sage Knox', 'Stanley Bradshaw', 'Kinsley Reeves', 'Ezequiel Friedman', 'Jaquan Best', 'Kennedi Calhoun', 'Edwin Hensley', 'Glenn Forbes', 'Jonas Diaz', 'Saniya Gibson', 'Alani Odonnell', 'Vaughn Merritt', 'Cristofer Cannon', 'Kenley Blackburn', 'Lillie Boyd', 'Denisse Ramos', 'Ruth Christian', 'Remington Chavez', 'Myles Burke', 'Aniya Wyatt', 'Kayla Moyer', 'Joseph Archer', 'Ibrahim Travis', 'Nia Villarreal', 'Kassandra Clarke', 'Jovany Glover', 'Keyon Blackburn', 'Derick Guzman', 'Ciara Montoya', 'Savannah Cline', 'Nick Tran', 'Ronald Burch', 'Chloe Howe', 'Jaylon Robbins', 'Maya Esparza', 'Bo Tanner', 'Manuel Spears', 'Zachariah Solis', 'Abdiel Ford', 'Skyler Buckley', 'Callum Wells', 'Tiffany Pittman', 'Dangelo Blair', 'Julian Conley', 'Mareli Ellis', 'Cameron Ashley', 'Micah Gould', 'Rihanna Pierce', 'Kadin Horn', 'Danny Medina', 'Mckinley Petersen', 'Avah Pugh', 'Giana Snyder', 'Layton Kidd', 'Kasey Pittman', 'Cheyenne Wright', 'Krystal Carlson', 'Tucker Little', 'Yosef Terry', 'Ainsley Orr', 'Brennen Pollard', 'Perla Young', 'Branden Li', 'Oscar Flowers', 'Vance Dalton', 'Maggie Molina', 'Yuliana Bailey', 'Jazmine Conner', 'Desiree Long', 'Joy Drake', 'Kendra Collins', 'Chance Acevedo', 'Ryder Donovan', 'Ryder Gonzales', 'Colt Austin', 'Hannah Lara', 'Kelvin Griffin', 'Shannon Flowers', 'Landyn Melton', 'Roland Clements', 'Emery Saunders', 'Ariel Schneider', 'Marquis Gibbs', 'Zechariah Guerrero', 'Destinee Mosley', 'Eric Johnson', 'Tanner Chase', 'Kirsten Blackwell', 'Cecilia Humphrey', 'Daisy Fernandez', 'Darren Reilly', 'Philip Morse', 'Haiden Odom', 'Adriel Dunn', 'Dayanara Middleton', 'Sharon Johnston', 'Damion Acosta', 'Valentina Deleon', 'Nasir Pratt', 'Aisha Galloway', 'Preston Woods', 'Nylah Patton', 'Paisley Mitchell', 'Trenton Gray', 'Alana Simon', 'Eliana Cox', 'Hazel Hart', 'Case Sharp', 'Alanna Brandt', 'Averie Juarez', 'Margaret Rodgers', 'Jaylynn Baldwin', 'Chaim Juarez', 'Reid Pearson', 'Olivia Cisneros', 'Jaden Preston', 'Scarlett Gardner', 'Chaim Preston', 'Zechariah Steele', 'Talon Donovan', 'Maddison Blackwell', 'Louis Jacobson', 'Yuliana Potter', 'Shea Castro', 'Lila Jones', 'Antony Tyler', 'Kaylah Werner', 'Oswaldo Berg', 'Kaila Andrade', 'Maren Bridges', 'Irene Erickson', 'Paisley Black', 'Claire Clark', 'Reynaldo Frank', 'Asa Webb', 'Kiara Morrow', 'Cason Mcdaniel', 'Giana Charles', 'William Beck', 'Joslyn Ibarra', 'Rowan Lawrence', 'Joaquin Roberson', 'Aniyah Taylor', 'Meadow Holt', 'Elianna Wiley', 'Rosa Little', 'Denise Lang', 'Madison Estrada', 'Ernesto Reid', 'Semaj Schultz', 'Parker Dalton', 'Sophia Mcdaniel', 'Nathalia Patel', 'Memphis Lindsey', 'Anabelle Vincent', 'Kaylin Herrera', 'Aylin Ingram', 'Victoria Myers', 'Lucas Cunningham', 'Darren Gomez', 'Nyasia Nichols', 'Regina Patton', 'Elias Pearson', 'Lucas Roberts', 'Deacon Allison', 'Finley Becker', 'Martha Phelps', 'Joy Huber', 'Jimmy Henry', 'Kobe Cochran', 'Sofia Fitzpatrick', 'Raven Brennan', 'Kenya Molina', 'Zack Mcdonald', 'Maribel Maxwell', 'India Keith', 'Taylor Vincent', 'Keith Bailey', 'Jenny Richardson', 'Randy Powell', 'Cael Morton', 'Jaycee Wilkinson', 'Jamya Kirby', 'Ricky Hurst', 'Bianca Lindsey', 'Solomon Phillips', 'Junior Wise', 'Koen Browning', 'Mira Holloway', 'Sanai Vazquez', 'Kaya Stone', 'Grady Rojas', 'Lawrence Lowery', 'Harmony Wilcox', 'Phoenix Duarte', 'Dayana Barber', 'Taylor Williams', 'Everett Gillespie', 'Urijah Mills', 'Brody Price', 'Kylie Shea', 'Landon Jefferson', 'Liberty Holt', 'Cristal Mcconnell', 'Jamarcus Duarte', 'Ben Roman', 'Kenyon Pratt', 'Sullivan Mora', 'Emerson Mccall', 'Bradyn Manning', 'Kendal Todd', 'Raquel Snow', 'Miracle Downs', 'Tia Macdonald', 'Judith Levy', 'Braeden Bryan', 'Sterling Morse', 'Lilia Mcguire', 'Damien Colon', 'Brielle Sherman', 'Evie Griffin', 'Sincere Vang', 'Trenton Murphy', 'Geovanni Conrad', 'Andrew Gamble', 'Alivia Beltran', 'Ronan Adams', 'Lillianna Morrow', 'Sandra Thompson', 'Giovani Rubio', 'Dominique Goodwin', 'Vance Stephenson']
            i = random.choice(alias).lower()
            name = i.split(" ")
            bbmail = i.replace(" ", "") + str(random.randint(10,1000)) + "@protocmail.me"
            bbpass = secrets.token_urlsafe(13)
            driver.find_elements(By.XPATH, '//*[@id="firstName"]')[0].send_keys(name[0])
            driver.find_elements(By.XPATH, '//*[@id="lastName"]')[0].send_keys(name[1])
            driver.find_elements(By.XPATH, '//*[@id="email"]')[0].send_keys(bbmail)
            driver.find_elements(By.XPATH, '//*[@id="fld-p1"]')[0].send_keys(bbpass)
            driver.find_elements(By.XPATH, '//*[@id="reenterPassword"]')[0].send_keys(bbpass)
            driver.find_elements(By.XPATH, '//*[@id="phone"]')[0].send_keys(phn())
            time.sleep(10)
            driver.find_elements(By.XPATH, '/html/body/div[1]/div/section/main/div[2]/div[1]/div/div/div/div/div/form/div[8]/button')[0].click()
            if self.debug:
                code.interact(local=locals())
            time.sleep(4)

            try:
                err = driver.find_elements(By.XPATH, '/html/body/div[1]/div/section/main/div[2]/div[1]/div/div/div/div[1]/div/strong/div/div')[0]
            except:
                break
            else:
                pass

        driver.get("https://www.bestbuy.com/site/customer/myaccount")

        try:
            driver.find_elements(By.XPATH, '//*[@id="shop-welcome-banner-1e0c39eb-299e-4039-b821-43a42368fc3b"]/div/div/div/div/div/div/div/h1')[0]
        except:
            self.status_signal.emit({'msg': "error creating a account account supposedly created", "status": "error"})
            if self.debug:
                code.interact(local=locals())
        else:
            self.status_signal.emit({'msg': "account created successfully", "status": "normal"})
            sbdata = supabase.table("bestbuy").insert({"owner": self.userid, "data":{"email": bbemail, "password": bbpass}}).execute()
            self.profile["email"] = bbmail
            self.profile["password"] = bbpass
            vurl = self.fetch_code(True)
            driver.get(vurl)
            try:
                self.selem_utils.wait_for_element_by_xpath(driver, "/html/body/center/div/table/tbody/tr/td/table/tbody/tr[4]/td/table/tbody/tr[4]/td/table/tbody/tr/td/a")
            except:
                self.status_signal.emit({'msg': "error verifying the account cannot find the verify account button", "status": "error"})
            else:
                driver.find_elements(By.XPATH, '/html/body/center/div/table/tbody/tr/td/table/tbody/tr[4]/td/table/tbody/tr[4]/td/table/tbody/tr/td/a')[0].click()
                time.sleep(3)
                driver.get("https://www.bestbuy.com/identity/accountSettings/page/email")
                if "<div>Verified</div>" in driver.page_source:
                    self.status_signal.emit({'msg': "account successfully verified", "status": "normal"})
                else:
                    self.status_signal.emit({'msg': "account is not verified", "status": "normal"})
                    if self.debug:
                        code.interact(local=locals())

    def fetch_code(self, acc_create=False): #does not fetch code for login verification
        self.status_signal.emit({'msg': "fetching code", "status": "normal"})
        mail = imaplib.IMAP4_SSL("mail.privateemail.com")
        mail.login("bot@protocmail.me", "123456789zzz")
        mail.select()


        while True:
            status, data = mail.search(None, 'FROM "bestbuy.com" TO "{}"'.format(self.profile["email"]))
            id_list = data[0].split()
            codes = []
            if len(id_list) == 0:
                return False
            if acc_create:
                self.status_signal.emit({'msg': "verifying account", "status": "normal"})
                regex = r'(https:\/\/view\.emailinfo2\.bestbuy\.com\/.*)'
                msg_subj = "Verify your email address"
            else:
                self.status_signal.emit({'msg': "fetching login code", "status": "normal"})
                regex = r'<span style="font-size:18px; font-weight:bold;">(.*?)</span>'
                msg_subj ="Your Password Reset verification code"


            for i in range(1, len(id_list) + 1):
                status, data = mail.fetch(id_list[-i], '(RFC822)')
                for response_part in data:
                    if isinstance(response_part, tuple):
                        message = email.message_from_bytes(response_part[1])
                        if msg_subj in message['subject']:
                            if message.is_multipart():
                                mail_content = ''
                                for part in message.get_payload():
                                    if part.get_content_type() == 'text/plain':
                                        mail_content += part.get_payload()
                            else:
                                mail_content = message.get_payload()
                            token = re.findall(regex, mail_content)[0]
                            print("token is :", token)
                            return token

    def handle_shipping(self):
        item = self.get_cart()
        try:
            itemid = item[0]["id"]
        except:
            raise Internalexp()

        if self.profile["fulfillment"] == "IN_STORE_PICKUP": 
            b4 = {"lineItems":[
               {
                  "id":itemid,
                  "serviceLevel":"NATIONAL",
                  "availableDate":"03/17/2022",
                  "storeFulfillmentType":"ShipToStore",
                  "type":"DEFAULT",
                  "selectedFulfillment":{
                     "inStorePickup":{
                        "pickupStoreId": self.store_id,
                        "displayDateType":"IN_HAND",
                        "isAvailableAtLocation":False,
                        "isSTSAvailable":True
                     }
                  }
               }
            ]}
            r = self.session.post("https://www.bestbuy.com/cart/api/v1/fulfillment/ispu".format(itemid), headers=self.header, json=b4)           
        else:
            r = self.session.put("https://www.bestbuy.com/cart/item/{}/fulfillment".format(itemid), headers=self.header, json={"selected": "SHIPPING"}) 
            self.add_address()

    def checkout(self):
        header = {'upgrade-insecure-requests': '1', 'dnt': '1', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36', 'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9', 'sec-fetch-site': 'same-origin', 'sec-fetch-mode': 'navigate', 'sec-fetch-user': '?1', 'sec-fetch-dest': 'document', 'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="98", "Google Chrome";v="98"', 'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"', 'referer': 'https://www.bestbuy.com/cart', 'accept-encoding': 'gzip, deflate, br', 'accept-language': 'en-US,en;q=0.9,fr;q=0.8,ar;q=0.7'}
        self.status_signal.emit({'msg': "checking out", "status": "normal"})
        
        try:
            self.handle_shipping()
        except Internalexp:
            self.status_signal.emit({'msg': "item is no longer in cart. trying again", "status": "normal"})
            self.clear_cart()
            self.atc(self.skuid)
            return self.checkout()
        r = self.session.post("https://www.bestbuy.com/cart/checkout", headers=header, data=None)           
        while True:
            u = "https://www.bestbuy.com/checkout/r/fast-tracks"
            r = self.session.get(u, headers=header)           
            if r.url == u:
                break
            else:
                self.status_signal.emit({'msg': "cookies expired refreshing session", "status": "normal"})
                self.login()
        try:
            clist = re.findall(r'"creditCards":(\[.*?\]),', r.text)[0]
        except:
            print("error card was not found on checkout page after being added")
            self.add_card()
            r = self.session.get("https://www.bestbuy.com/checkout/r/fast-tracks", headers=header)           
        else:
            data = parse(clist)
            for c in data:
                if self.profile["ccnum"][12:] == c["number"][4:]:
                    self.ccid = c["id"]
        self.header["referer"] = "https://www.bestbuy.com/checkout/r/fast-track"
        try:
            orderid = re.findall(r'"customerOrderId":"(.*?)",', r.text)[0]
            number = re.findall(r'"number":"(.*?)",', r.text)[0]
            pid = re.findall(r'"payment":{"id":"(.*?)"}', r.text)[0]
            order_token = re.findall(r'orderData = {"id":"(.*?)"', r.text)[0]
            itemid = re.findall(r'"items":\[{"id":"(.*?)",', r.text)[0]
        except:
            print(r.text)
        if self.profile["fulfillment"] == "SHIPPING":
            # b4 = { "items":[ { "id": itemid, "type":"DEFAULT", "selectedFulfillment":{ "shipping":{ "address":{ "lastName": self.profile["lname"], "street": self.profile["adr1"], "city": self.profile["city"], "zipcode": self.profile["zipcode"], "street2": self.profile["adr2"], "middleInitial": self.profile["mname"], "state": self.profile["state"], "saveToProfile":False, "country": self.profile["country"], "id": self.adr_id, "dayPhoneNumber": self.profile["phone"], "firstName": self.profile["name"], "setAsPrimaryShipping":True, "useAddressAsBilling":False } } }, "giftMessageSelected":False } ] }
            b4 = {"selectedFulfillment": {"shipping": {"levelOfService": "1"}}}
            r = self.session.patch("https://www.bestbuy.com/checkout/orders/{}/items/{}".format(order_token, itemid), headers=self.header, json=b4)           
        


        header = {'accept': 'application/json, text/javascript, */*; q=0.01', 'accept-encoding': 'gzip, deflate, br', 'accept-language': 'en-US,en;q=0.9,fr;q=0.8,ar;q=0.7', 'cache-control': 'no-cache', 'content-type': 'application/json', 'dnt': '1', 'order_token': order_token, 'origin': 'https://www.bestbuy.com', 'pragma': 'no-cache', 'referer': 'https://www.bestbuy.com/checkout/r/fast-track', 'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="98", "Google Chrome";v="98"', 'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"', 'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-origin', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36', 'x-client': 'CHECKOUT_VIEW', 'x-context-id': orderid, 'x-pay-visibility-clientpage': 'fast-track', 'x-pay-visibility-user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36'}
        r = self.session.patch("https://www.bestbuy.com/checkout/orders/{}/".format(order_token), headers=self.header, json={"phoneNumber": self.profile["phone"],"smsNotifyNumber": self.profile["phone"],"smsOptIn":True})           
        if r.status_code == 412:
            data = parse(r.text)
            try:
                err = data["errors"][0]["errorMessage"].replace("<!-- (#0724-S) -->", "")
            except:
                self.status_signal.emit({'msg':  'error retrieving error message, proceeding', "status": "normal"})
            else:
                self.status_signal.emit({'msg':  err, "status": "normal"})
                self.status_signal.emit({'msg': 'error adding phone number, proceeding with order' , "status": "normal"})
        b = { "billingAddress":{ "firstName": self.profile["name"], "lastName":self.profile["lname"], "addressLine1":self.profile["adr1"], "addressLine2":self.profile["adr2"], "city":self.profile["city"], "state":self.profile["state"], "postalCode":self.profile["zipcode"], "country":self.profile["country"], "dayPhone":self.profile["phone"], "standardized":False, "userOverridden":True, "emailAddress":"" }, "creditCard":{ "number":number, "expMonth":self.profile["expm"], "expYear":self.profile["expy"], "cvv":self.profile["ccv"], "type": self.profile["cctype"], "creditCardProfileId":self.ccid, "saveToProfile":False, "default":False, "virtualCard":False, "orderId":orderid, "appliedPoints":None }}
        r = self.session.put("https://www.bestbuy.com/payment/api/v1/payment/{}/creditCard".format(pid), headers=header, json=b)   
        
        if r.status_code == 404:#might not be enough
            r = self.session.put("https://www.bestbuy.com/payment/api/v1/payment/{}/creditCard".format(pid), headers=header, json=b)   
        r = self.session.post("https://www.bestbuy.com/checkout/orders/{}/paymentMethods/refreshPayment".format(pid), headers=header, json={})   
        b2 = {"browserInfo":{"colorDepth":"24","height":"984","javaEnabled":False,"language":"en-US","timeZone":"-60","userAgent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36","width":"984"}}
        header = {'accept': 'application/com.bestbuy.order+json', 'accept-encoding': 'gzip, deflate, br', 'accept-language': 'en-US,en;q=0.9,fr;q=0.8,ar;q=0.7', 'cache-control': 'no-cache', 'content-type': 'application/json', 'dnt': '1', 'origin': 'https://www.bestbuy.com', 'pragma': 'no-cache', 'referer': 'https://www.bestbuy.com/checkout/r/fast-track', 'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="98", "Google Chrome";v="98"', 'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"', 'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-origin', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36', 'x-user-interface': 'DotCom-Optimized'}
        r = self.session.post("https://www.bestbuy.com/checkout/orders/{}/".format(order_token), headers=header, json=b2)   
        data = json.loads(r.text)
        try:
            if len(data["errors"]) != 0:
                self.status_signal.emit({'msg': "error placing order", "status": "error"})
                self.status_signal.emit({'msg': "error message: {}".format(data["errors"][0]["errorMessage"]), "status": "error"})
                return { "success": False, "message": str(data["errors"][0]["errorMessage"]),"log" : {}}
        except:
            self.status_signal.emit({'msg': "order placed successfully", "status": "normal"})
            return {"success" : True }

    def update_cookies(self, cookies): #updates session cookies 
        self.session.cookies.clear()
        for j in cookies:
            self.session.cookies.set(j["name"], j["value"])

    def check_account(self):
        user = self.supabase.table("bestbuy").select("data").match({"owner": self.userid}).execute()        
        if len(user.data) != 0:
            self.profile["email"] = user.data[0]["data"]["email"]
            self.profile["password"] = user.data[0]["data"]["password"]
        else:
            print("account not found creating new one")
            # self.create_bb()

    def watch_or_buy(self):

        self.check_account()
        while not self.check_stock(self.skuid):
            time.sleep(60*2) #will sleep for 2mins

        d = self.login()
        self.update_cookies(cookies)
        self.update_location()
        d = webdriver.Chrome()
        d.get("https://bestbuy.com")
        for i in cookies:
            d.add_cookie(i)
        self.add_card(d)
        self.clear_cart()
        self.atc(self.skuid)
        return self.checkout()




class Stat:

    def emit(self, a):#can be used to implement a way to talk to api
        print(a["msg"])

