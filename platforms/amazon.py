import requests, random, time, os, re, string, json 
import undetected_chromedriver as webdriver
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.ssl_ import create_urllib3_context
from bs4 import BeautifulSoup
from twocaptcha import TwoCaptcha
from server.src.utils.exceptions import Authexp



# prid is purchaseid
# pid is payment id
# some http responses are passed between functions as self.response so we dont make duplicate requests
#and in other functions we pass http response as a function parameter to retrieve data from that response in another function so we also dont make duplicate requests and
#leave everything organized  
# address (both billing and shipping) should be in the form 
# adr = shipping address adr2 = billing
# adr = {
#   "adr1": "2909 Adams Dr",
#   "adr2": "",
#   "city" : "Melissa",
#   "region": "TX",
#   "postalcode": "75454",
#   "countrycode": "US",
#   "adrfullname": "hmed chiboub",
#   "phonenm": "(480) 834-9700",
# }
# payment info should be in the form
# ccinfo = {
# "cnum": "1234+1234+1234+1234", 
# "ccname": "samir chiboub",
# "expy": "2027",
# "expm": "12"
# }
#product must be entire url to a product example: https://www.amazon.com/TOZO-T6-Bluetooth-Headphones-Waterproof/dp/B07RGZ5NKS/ thats it 


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

class Amazon:
    def __init__(self, email, password, product, adr, adr2, ccinfo, stat, capkey):
        self.status_signal = stat
        self.cookies = ""
        self.client = requests.session()
        self.email = email
        self.password = password
        self.product = product
        self.ccinfo = ccinfo
        # self.client.proxies = {"https": "https://localhost:8080"}
        # self.client.verify = False
        self.adr = adr
        self.adr2 = adr2  
        self.prid = ""
        self.adrid = "" #shipping address id
        self.client.mount('https://www.amazon.com/', CipherAdapter())
        self.solver = TwoCaptcha(capkey)
        self.status_signal.emit({"msg": "Starting Bot", "status": "normal"})
        self.header = {
                "cache-control":    "max-age=0",
                "rtt":  "300",
                "downlink": "1.55",
                "ect":  "3g",
                "sec-ch-ua":    '" Not A;Brand";v="99", "Chromium";v="96", "Google Chrome";v="96"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform":   "Windows",
                "dnt":  "1",
                "upgrade-insecure-requests":    "1",
                "user-agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
                "accept":   "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                "sec-fetch-site":   "same-origin",
                "sec-fetch-mode":   "navigate",
                "sec-fetch-user":   "?1",
                "sec-fetch-dest":   "document",
                "referer":  "https://www.amazon.com/",
                "accept-encoding":  "gzip, deflate, br",
                "accept-language":  "en-US,en;q=0.9,fr;q=0.8,ar;q=0.7",
        } 


    def selogin(self, email, password):
        self.status_signal.emit({"msg": "loging in", "status": "normal"})
        driver = webdriver.Chrome()
        driver.get("https://www.amazon.com/ap/signin?_encoding=UTF8&openid.assoc_handle=usflex&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.mode=checkid_setup&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&openid.ns.pape=http%3A%2F%2Fspecs.openid.net%2Fextensions%2Fpape%2F1.0&openid.pape.max_auth_age=0")
        driver.find_element_by_xpath('//*[@id="ap_email"]').send_keys(email)
        try:
            captcha = driver.find_element_by_xpath('//*[@id="auth-captcha-image"]').get_attribute("src")
            while(captcha):
                self.status_signal.emit({"msg": "captcha found proceeding", "status": "normal"})
                try:
                    captcha = driver.find_element_by_xpath('//*[@id="auth-captcha-image"]').get_attribute("src")
                    result = self.solver.normal(captcha)
                    captcha = driver.find_element_by_xpath('//*[@id="auth-captcha-guess"]')
                    captcha.send_keys(result["code"])
                    driver.find_element_by_xpath('//*[@id="continue"]').click()
                except Exception as ex:
                    # print(ex)
                    break
        except Exception as ex:
            driver.find_element_by_xpath('//*[@id="continue"]').click()
            # print(ex)



        try:
            driver.find_element_by_css_selector("#auth-error-message-box > div > div > ul > li > span").text
            #email is incorect
        except Exception as ex :
            pass
            # print(ex)
        else:
            raise Authexp({"message": "email is incorect"})
        driver.find_element_by_xpath('//*[@id="ap_password"]').send_keys(password)
        driver.find_element_by_xpath('//*[@id="signInSubmit"]').click()


        while True:
            try:
                errorcap = driver.find_element_by_xpath('//*[@id="auth-error-message-box"]/div/div/ul/li/span').text
                if errorcap.strip() == 'Enter the characters as they are given in the challenge.':
                    self.status_signal.emit({"msg": "error solving captcha trying again", "status": "normal"})
                    driver.find_element_by_xpath('//*[@id="signInSubmit"]').click()
            except Exception as ex:
                # print("captcha error not found:") #means that either login success or first time logging in
                # print(ex)
                pass
            
            try:
                captcha = driver.find_element_by_xpath('//*[@id="auth-captcha-image"]').get_attribute("src")
                result = self.solver.normal(captcha)
                driver.find_element_by_xpath('//*[@id="ap_password"]').send_keys(password)
                captcha = driver.find_element_by_xpath('//*[@id="auth-captcha-guess"]')
                captcha.send_keys(result["code"])
                driver.find_element_by_xpath('//*[@id="signInSubmit"]').click()

            except Exception as ex:
                # print(ex) 
                self.status_signal.emit({"msg": "no captcha found proceeding", "status": "normal"})
                break #break when theres no captcha 
                #sometimes captcha result is wrong only move on when there is no captcha to be solved

        # check if password is wrong
        try: 
            error = driver.find_element_by_xpath('//*[@id="auth-error-message-box"]/div/div/ul/li/span').text
            # if error.strip() == "Your password is incorrect": 
                
        except Exception as ex:
            pass
            # print(ex)
        else:
            raise Authexp({"message" : "password is incorrect"})


        t = 0
        while(True):
            try:
                x = driver.find_element_by_css_selector('#body > div > div > div.a-section.a-spacing-medium > span').text
            except Exception as ex:
                # print("ex is :" + str(ex))
                break
            else:
                self.status_signal.emit({"msg": "bot waiting for login request to be approved", "status": "normal"})
                time.sleep(60) #login request need to be accepted from email
                driver.refresh()
                t += 1
            if t == 20: #will wait for 20 minutes if login not validated wil return a error
                raise Authexp({"message": "login request was not approved from email exiting"})
                break
        try:
            driver.find_element_by_xpath('//*[@id="auth-account-fixup-phone-form"]/div/h1')
            driver.find_element_by_xpath('//*[@id="ap-account-fixup-phone-skip-link"]').click()
        except Exception as ex:
            pass

        try:
            driver.find_element_by_xpath('//*[@id="alert-0"]/div[1]/div/div/h4').text
        except:
            pass
        else:
            raise Authexp({"message": "account is on hold"})

        # used to retrieve encrypted password using mitm depreceated
        # body = {} 
        # for request in driver.requests:
        #   if "https://www.amazon.com/ap/signin" in request.url:
        #       for i in request.body.decode("utf-8").split("&"):
        #           j = i.split("=")
        #           try:
        #               body[j[0]] = j[1]
        #               if "encryptedPwd" in body:
        #                   self.encpwd = body["encryptedPwd"]
        #                   break
        #           except:
        #               pass
        #       if self.encpwd != "":
        #           break
        #remove when db is implemented for useres
        # fname = self.desktop.replace("\\", "/") + "/amazonpwd.txt"
        # if not os.path.isfile(fname):
        #   print(self.encpwd)
        #   fp = open(fname, "w")
        #   fp.write("pass:" + str(encpwd))
        #   fp.close()
        # print(self.cookies)
        # input()
        # driver.quit()
        self.cookies = driver.get_cookies()

    def login(self, email, password): #depreceated
        resp = self.client.get('https://www.amazon.com/ap/signin?_encoding=UTF8&openid.assoc_handle=usflex&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.mode=checkid_setup&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&openid.ns.pape=http%3A%2F%2Fspecs.openid.net%2Fextensions%2Fpape%2F1.0&openid.pape.max_auth_age=0&openid.return_to=https%3A%2F%2Fwww.amazon.com%2Fgp%2Fyourstore%2Fhome%3Fie%3DUTF8%26action%3Dsign-out%26path%3D%252Fgp%252Fyourstore%252Fhome%26ref_%3Dnav_AccountFlyout_signout%26signIn%3D1%26useRedirectOnSuccess%3D1', headers=self.header)
        soup = BeautifulSoup(resp.text, 'html.parser')
        payload = {
            "appActionToken": soup.find('input', {'name': 'appActionToken'})["value"],
            "appAction": "SIGNIN_PWD_COLLECT",
            "subPageType": "SignInClaimCollect",
            "openid.return_to": soup.find('input', {'name':'openid.return_to'})["value"],
            "prevRID": soup.find('input', {'name':'prevRID'})["value"],
            "workflowState": soup.find('input', {'name':'workflowState'})["value"],
            "email": email,
            "password": "",
            "create": "0",
                    }
        resp = self.client.post('https://www.amazon.com/ap/signin', data=payload, headers=self.header)
        soup = BeautifulSoup(resp.text, 'html.parser')
        payload = {
            "appActionToken": soup.find('input', {'name':'appActionToken'})["value"],
            "appAction": "SIGNIN_PWD_COLLECT",
            "metadata1": "true",
            "openid.return_to": "ape:aHR0cHM6Ly93d3cuYW1hem9uLmNvbS9ncC95b3Vyc3RvcmUvaG9tZT9pZT1VVEY4JmFjdGlvbj1zaWduLW91dCZwYXRoPSUyRmdwJTJGeW91cnN0b3JlJTJGaG9tZSZyZWZfPW5hdl9BY2NvdW50Rmx5b3V0X3NpZ25vdXQmc2lnbkluPTEmdXNlUmVkaXJlY3RPblN1Y2Nlc3M9MQ==",
            "prevRID": soup.find('input', {'name':'prevRID'})["value"],
            "workflowState": soup.find('input', {'name':'workflowState'})["value"],
            "email": email,
            "email": email,
            "encryptedPwd": self.encpwd,
            "encryptedPasswordExpected": "",
        }
        print(payload)
        resp = self.client.post('https://www.amazon.com/ap/signin', headers=self.header, data=payload)
        soup = BeautifulSoup(resp.text, 'html.parser')
        # addphone = soup.find('input', {'name':'cvf_phone_num'})
        if "To better protect your account" in retype.strip():
            print("captcha code presented")
            # pass# since we need to type captcha code to login

            # self.selogin()
        passreset = soup.find('h2', {'class':'a-text-normal'})
        if passreset:
            raise Authexp({"message": "passsword reset forced"})
        if  "session-token" in resp.headers["Set-Cookie"] :
            print("cookies expired")
            raise Authexp({"message": "login not successful"})
        else:
            print("logged in sucs")

    def load_cookies(self): #pass cookies from selenium to client session
        for cookie in self.cookies:
            self.client.cookies.set(cookie['name'], cookie['value'])
        resp = self.client.get('https://www.amazon.com/gp/your-account/order-history?ref_=ya_d_c_yo', headers=self.header)
        soup = BeautifulSoup(resp.text, 'html.parser')
        yorders = soup.find('section', {'class':'your-orders-content-container aok-relative js-yo-container'})
        if yorders == None :
            # try:
            self.selogin("email", "password")
            # except Authexp as ex:
            #   message = ex.args[0]
            #   self.status_signal.emit({"msg": message, "status": "error"})
                #return message to api
        else:
            print("logged in sucs")

    def delete_cart(self): #deletes old cart so we dont checkout with older items
        self.status_signal.emit({"msg": "clearing cart", "status": "normal"})
        req1 = self.client.get("https://www.amazon.com/gp/cart/view.html?ref_=nav_cart", headers=self.header)
        soup = BeautifulSoup(req1.text, 'html.parser')
        try:
            aitems = soup.find('div', {'data-name': 'Active Items'})
            items = []
            for i in aitems:
                try:
                    items.append(i["data-itemid"] + "|1|0|1|49|||0|||1")
                except Exception as ex:
                    pass        
        except: #cart is already empty
            pass
        else:
            for i in items:
                payload4 = {
                    "hasMoreItems": "false",
                    "timeStamp": soup.find('input', {'name': "timeStamp"})["value"],
                    "requestID": soup.find('input', {'name': "requestID"})["value"],
                    "token": soup.find('input', {'name': "token"})["value"],
                    "activeItems": i,
                    "addressId": "",
                    "addressZip": "",
                    "closeAddonUpsell": "1",
                    "submit.cart-actions": "1",
                    "pageAction": "cart-actions",
                    "actionPayload": '[{"type":"DELETE_START","payload":{"itemId":"'+i[:37]+'","list":"activeItems","relatedItemIds":[],"isPrimeAsin":false}}]',
                    "displayedSavedItemNum": "0",
                }
                req1 = self.client.post("https://www.amazon.com/gp/cart/ajax-update.html/ref=ox_sc_pc_b1", headers=self.header, data=payload4)

    def place_to_cart(self, product):
        self.status_signal.emit({"msg": "adding item to cart", "status": "normal"})
        req = self.client.get(product, headers=self.header)
        soup = BeautifulSoup(req.text, 'html.parser')
        try:
            x = soup.find("span", {"class": "a-color-error"}).get_text().strip()
        except:
            pass        
        else:
            if x == "This item cannot be shipped to your selected delivery location. Please choose a different delivery location.":
                raise Authexp({"message": "item cannot be shipped to this address"})
        yorders = soup.find('form', {'action':re.compile(r'.*/gp/product/handle-buy-box/ref=.*')})
        payload = {}
        for i in yorders:
            try:
                if (i["type"] == "hidden"):
                    payload[i["name"]] = i["value"] 
            except Exception as ex:
                pass
        req = self.client.post("https://www.amazon.com/gp/product/handle-buy-box/ref=dp_start-bbf_1_glance", headers=self.header, data=payload)
        if req.status_code == 200:
            self.status_signal.emit({"msg": "item added", "status": "normal"})
    
    def initiate_checkout(self):
        cartid = ''.join(random.choice(string.digits) for _ in range(13))
        self.response1  = self.client.get("https://www.amazon.com/gp/cart/desktop/go-to-checkout.html/ref=ox_sc_proceed?partialCheckoutCart=1&isToBeGiftWrappedBefore=0&proceedToRetailCheckout=Proceed+to+checkout&proceedToCheckout=1&cartInitiateId=" + cartid, headers=self.header)

    def check_stock(self):
        req = self.client.get(self.product, headers=self.header)
        aval = re.findall(r"title=\"Add to Shopping Cart\"", req.text)
        aval2 = re.findall(r"This item cannot be shipped to your selected delivery location. Please choose a different delivery location", req.text)
        aval3 = re.findall(r"Your selected delivery location is beyond seller's shipping coverage for this item. Please choose a different delivery location or purchase from another seller", req.text)
        if len(aval) != 0 or len(aval2) != 0 or len(aval3) != 0 :
            self.status_signal.emit({"msg": "item in stock, proceeding", "status": "normal"})
            return True  
        else:
            self.status_signal.emit({"msg": "item not in stock, sleeping", "status": "normal"})
            return False

    def deselect_cart(self):
        self.status_signal.emit({"msg": "clearing cart", "status": "normal"})
        req1 = self.client.get("https://www.amazon.com/gp/cart/view.html?ref_=nav_cart", headers=self.header)
        soup = BeautifulSoup(req1.text, 'html.parser')
        try:
            aitems = soup.find('div', {'data-name': 'Active Items'})
            items = []
            for i in aitems:
                try:
                    items.append(i["data-itemid"] + "|1|0|1|49|||0|||1")
                except Exception as ex:
                    pass

        except: #cart is already empty
            pass
        
        payload4 = {
            "hasMoreItems": "false",
            "timeStamp": soup.find('input', {'name': "timeStamp"})["value"],
            "requestID": soup.find('input', {'name': "requestID"})["value"],
            "token": soup.find('input', {'name': "token"})["value"],
            "activeItems": items,
            "addressId": "",
            "addressZip": "",
            "closeAddonUpsell": "1",
            "pageAction": "deselect-all-items-for-checkout",
            "actionType": "deselect-all-items-for-checkout",
            "submit.deselect-all-items-for-checkout": "1",
            "shouldPreserveImb": "1",
        }
        req1 = self.client.post("https://www.amazon.com/gp/cart/ajax-update.html/ref=ox_sc_pc_b1", headers=self.header, data=payload4)
        self.status_signal.emit({"msg": "cart cleared", "status": "normal"})

    def add_payment(self, obj): #first get method is already made on checkout will return the billing address page 
        self.status_signal.emit({"msg": "Adding Payment Info", "status": "normal"})
        req1 = self.client.get("https://www.amazon.com/gp/buy/payselect/handlers/display.html?hasWorkingJavascript=1", headers=self.header)
        soup = BeautifulSoup(req1.text, 'html.parser')
        token = soup.find('input', {'name': 'ppw-widgetState'})
        customerid = re.findall(r"customerId: (.*)", req1.text)[0]
        payload1 = "ppw-widgetEvent%3AAddCreditCardEvent=&ppw-jsEnabled=True&ppw-widgetState="+ token["value"] +"&ie=UTF-8&addCreditCardNumber="+ str(obj["cnum"]) +"&ppw-accountHolderName="+ obj["ccname"] +"&ppw-expirationDate_month="+ str(obj["expm"]) +"&ppw-expirationDate_year=" + str(obj["expy"]) 
        header = {
            "Host": "apx-security.amazon.com",
            "Connection":   "keep-alive",
            "Content-Length":   "2912",
            "sec-ch-ua":    '" Not A;Brand";v="99", "Chromium";v="96", "Google Chrome";v="96"',
            "DNT":  "1",
            "Widget-Ajax-Attempt-Count":    "0",
            "sec-ch-ua-mobile": "?0",
            "User-Agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept":   "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "APX-Widget-Info":  "Checkout/desktop/b6xNjpBUfA7g",
            "sec-ch-ua-platform":   "Windows",
            "Origin":   "https://apx-security.amazon.com",
            "Sec-Fetch-Site":   "same-origin",
            "Sec-Fetch-Mode":   "cors",
            "Sec-Fetch-Dest":   "empty",
            "Referer":  "https://apx-security.amazon.com/cpe/pm/register",
            "Accept-Encoding":  "gzip, deflate, br",
            "Accept-Language":  "en-US,en;q=0.9,fr;q=0.8,ar;q=0.7",
        }
        req2 = self.client.post("https://apx-security.amazon.com/payments-portal/data/f1/widgets2/v1/customer/"+ customerid.replace("'", "") +"/continueWidget?sif_profile=APX-Encrypt-All-NA", headers=header, data=payload1)
        try:
            data = json.loads(req2.text)
        except:
            print("exception occured could not replicate it")
            self.status_signal.emit({"msg": "error adding payment", "status": "normal"})
            raise Exception()
        try:
            pid = data["additionalWidgetResponseData"]["additionalData"]["paymentInstrumentId"]
        except:#error adding cc
            raise Authexp({"message":"error adding cc"})
        else:
            header = {
                "accept": "text/plain, */*; q=0.01",
                "accept-encoding": "gzip, deflate, br",
                "accept-language": "en-US,en;q=0.9",
                "content-length": "5027",
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8;",
                "downlink": "7.65",
                "ect": "4g",
                "origin": "https://www.amazon.com",
                "referer": "https://www.amazon.com/gp/buy/payselect/handlers/display.html?hasWorkingJavascript=1",
                "rtt": "150",
                "sec-ch-ua": '" Not;A Brand";v="99", "Google Chrome";v="97", "Chromium";v="97"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": "Windows",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36",
                "x-amz-checkout-transition": "ajax",
                "x-requested-with": "XMLHttpRequest"
            }
            self.response2 = self.client.post("https://www.amazon.com/gp/buy/shared/handlers/async-continue.html", data="ppw-widgetState="+ str(token["value"]) +"&ie=UTF-8&ppw-instrumentRowSelection=instrumentId%3D"+ pid +"%26isExpired%3Dfalse%26paymentMethod%3DCC%26tfxEligible%3Dfalse&ppw-"+ pid +"_pcardReferenceNumber=&ppw-jsEnabled=true&ppw-widgetEvent%3ASetPaymentPlanSelectContinueEvent=&hasWorkingJavascript=1&isAsync=1&isClientTimeBased=1&handler=/gp/buy/payselect/handlers/apx-submit-continue.html", headers=header)
            #reponse2 will be used in add billing to save us from making a dumplicate request
            return pid
    
    def add_address(self, obj1, req1):
        # req1 = client.get("https://www.amazon.com/gp/buy/addressselect/handlers/display.html?hasWorkingJavascript=1#new-address", headers=header)
        #req1 commented out so we can use this function in more than one place
        self.status_signal.emit({"msg": "Adding Address", "status": "normal"})
        soup = BeautifulSoup(req1.text, 'html.parser')
        payload = {
            "address-ui-widgets-countryCode": obj1["countrycode"],
            "address-ui-widgets-enterAddressFullName": obj1["adrfullname"],
            "address-ui-widgets-enterAddressPhoneNumber": obj1["phonenm"],
            "address-ui-widgets-enterAddressLine1": obj1["adr1"],
            "address-ui-widgets-enterAddressLine2": obj1['adr2'],
            "address-ui-widgets-enterAddressCity": obj1['city'],
            "address-ui-widgets-enterAddressStateOrRegion": obj1['region'],
            "address-ui-widgets-enterAddressPostalCode": obj1['postalcode'],
            "address-ui-widgets-previous-address-form-state-token": soup.find('input', {'name': 'address-ui-widgets-previous-address-form-state-token'}),
            "address-ui-widgets-delivery-instructions-desktop-expander-context": {"deliveryInstructionsDisplayMode" : "CDP_ONLY", "deliveryInstructionsClientName" : "RetailWebsite", "deliveryInstructionsDeviceType" : "desktop", "deliveryInstructionsIsEditAddressFlow" : "false"},
            "address-ui-widgets-addressFormButtonText": "useThisAddress",
            "address-ui-widgets-addressFormHideHeading": "false",
            "address-ui-widgets-addressFormHideSubmitButton": "false",
            "address-ui-widgets-enableAddressDetails": "true",
            "address-ui-widgets-returnLegacyAddressID": "false",
            "address-ui-widgets-enableDeliveryInstructions": "true",
            "address-ui-widgets-enableAddressWizardInlineSuggestions": "true",
            "address-ui-widgets-enableEmailAddress": "false",
            "address-ui-widgets-enableAddressTips": "false",
            "address-ui-widgets-amazonBusinessGroupId": "",
            "address-ui-widgets-clientName": "RetailWebsite",
            "address-ui-widgets-enableAddressWizardForm": "true",
            "address-ui-widgets-delivery-instructions-data": {"initialCountryCode":"US"},
            "address-ui-widgets-address-wizard-interaction-id": soup.find('input', {'name': 'address-ui-widgets-address-wizard-interaction-id'}),
            "address-ui-widgets-obfuscated-customerId": soup.find('input', {'name': 'address-ui-widgets-obfuscated-customerId'}),
            "address-ui-widgets-locationData": "",
            "address-ui-widgets-enableLatestAddressWizardForm": "false",
            "address-ui-widgets-avsSuppressSoftblock": "false",
            "address-ui-widgets-avsSuppressSuggestion": "false",
            "address-ui-widgets-locale": "",
            "hasWorkingJavascript": "1",
            "purchaseId": soup.find('input', {'name': 'purchaseId'}),
        }
        req2 = self.client.post("https://www.amazon.com/a/addresses/ajax/widgets/create", headers=self.header, data=payload)
        data = json.loads(req2.text)
        adrid = data["createOrEditAddressResponse"]["addressId"]# address id can be either shipping or billing  
        if adrid != None: 
            self.status_signal.emit({"msg": "Address Is Added", "status": "normal"})
            return adrid
        else:
            raise Authexp({"message": "address is incorrect"}) #will return a adressid if successful a expetion otherwise

    def validate_address(self, adrid): #will validate the shipping address without this function we wouldnt be able to go to next page in the checkout also this function return the payment select page
        try:
            self.prid  = re.findall(r'name="purchaseId" value="(.*?)"',self.response1.text)[0]
        except:
            self.status_signal.emit({"msg": "error validating address cart is empty", "status": "normal"})
            return 
        req2 = self.client.get("https://www.amazon.com/gp/buy/addressselect/handlers/continue.html/ref=ox_shipaddress_ship_to_this_2?ie=UTF8&action=select-shipping&addressID="+str(adrid)+"&enableDeliveryPreferences=1&fromAnywhere=0&isCurrentAddress=0&numberOfDistinctItems=1&purchaseId="+str(self.prid)+"&requestToken=&hasWorkingJavascript=1", headers=self.header)
        
    def change_location(self, obj):
        self.status_signal.emit({"msg": "changing location to specified zipcode", "status": "normal"})
        req = self.client.get("https://www.amazon.com/", headers=self.header) 
        token = re.findall(r'{&quot;anti-csrftoken-a2z&quot;:&quot;(.*?)&quot;}', req.text)
        header = {
            "accept": "text/html,*/*",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en-US,en;q=0.9,fr;q=0.8,ar;q=0.7",
            "anti-csrftoken-a2z": token[0],
            "dnt": "1",
            "downlink": "10",
            "ect": "4g",
            "referer": "https://www.amazon.com/",
            "rtt": "250",
            "sec-ch-ua": '" Not;A Brand";v="99", "Google Chrome";v="97", "Chromium";v="97"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "Windows",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36",
            "x-requested-with": "XMLHttpRequest",
        }
        req = self.client.get("https://www.amazon.com/gp/glow/get-address-selections.html?deviceType=desktop&pageType=Detail&storeContext=electronics&actionSource=desktop-modal", headers=header) 
        token = re.findall(r'CSRF_TOKEN : "(.*?)"', req.text)[0]
        payload2 = "locationType=LOCATION_INPUT&zipCode="+ obj["postalcode"] +"&storeContext=generic&deviceType=web&pageType=Gateway&actionSource=glow&almBrandId=undefined"
        header = {
            "accept": "text/html,*/*",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en-US,en;q=0.9",
            "anti-csrftoken-a2z": token,
            "content-length": "133",
            "content-type": "application/x-www-form-urlencoded",
            "contenttype": "application/x-www-form-urlencoded;charset=utf-8",
            "downlink": "10",
            "ect": "4g",
            "origin": "https://www.amazon.com",
            "referer": "https://www.amazon.com/?",
            "rtt": "250",
            "sec-ch-ua": '" Not;A Brand";v="99", "Google Chrome";v="97", "Chromium";v="97"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "Windows",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36",
            "x-requested-with": "XMLHttpRequest",
        }
        req = self.client.post("https://www.amazon.com/gp/delivery/ajax/address-change.html", data=payload2, headers=header) 
        data = json.loads(req.text)
        if data["isValidAddress"] == 0:
            #either a wrong zipcode or not a us zipcode
            self.status_signal.emit({"msg": "wrong zipCode or not a valid one", "status": "normal"})


    def add_billing(self, obj): 
        self.status_signal.emit({"msg": "Adding billing address", "status": "normal"})
        adrid = self.add_address(obj, self.response2) #request is the billing address page from the add_payment method
        payload = {
            "paymentInstrumentId": self.pid,
            "paymentMethodCode": "CC",
            "action": "select-billing",
            "isAUIWSAddressCreationWorkflow": "1",
            "addressID": adrid,
            "purchaseId": self.prid,
            "isClientTimeBased": "1",
            "handler": "/gp/buy/billingaddressselect/handlers/continue.html"
        }
        req2 = self.client.post("https://www.amazon.com/gp/buy/shared/handlers/async-continue.html/ref=ox_billing_continue", headers=self.header, data=payload)
        self.status_signal.emit({"msg": "billing address added", "status": "normal"})
    
    def checkout(self): #must initiate cart before
        self.status_signal.emit({"msg": "checking out", "status": "normal"})
        req = self.client.get("https://www.amazon.com/gp/buy/spc/handlers/display.html?hasWorkingJavascript=1", headers=self.header)
        soup = BeautifulSoup(req.text, 'html.parser')
        try:
            prime_prompt = soup.find('div', {'class': "updp-left-option no-thanks-link"})
            proceed = soup.find('a', {'class': "prime-nothanks-button prime-checkout-continue-link primeEvent checkout-continue-link a-button-text"})["href"]
            req1 = self.client.get('https://www.amazon.com/' + proceed, headers=self.header)
            soup = BeautifulSoup(req1.text, 'html.parser')
        except Exception as ex:#passing the get prime prompt
            pass #exception will occur when there is no prompt and we just pass
        try:
            yorders = soup.find('form', {'id': "spc-form"})
            fnode = yorders.find('span', {'id': "spc-form-inputs"})
        except Exception as ex: #order not placed to cart
            pass
        payload2 = {}
        try:
            fnode = yorders.findAll('input', {'type': "hidden"})
        except:
            self.status_signal.emit({"msg": "error checking out cart is empty", "status": "normal"})
            return
        for i in fnode:
            try:        
                payload2[i["name"]] = i["value"] 
            except:
                pass
        payload2["hasWorkingJavascript"] = 1
        payload2["placeYourOrder1"] = 1
        if "amazon" not in yorders["action"]:
            url = "https://www.amazon.com" + yorders["action"]
        else:
            url = yorders["action"]
        placeod = self.client.post(url, headers=self.header, data=payload2)
        soup = BeautifulSoup(placeod.text, 'html.parser')
        url = soup.find('meta')["content"][7:]
        if "duplicate-order" in url:
            url = "https://www.amazon.com" + url
            req = self.client.get(url, headers=self.header)
            soup = BeautifulSoup(req.text, 'html.parser')
            form = soup.find('form', {'class': "a-declarative"})
            payload = {}
            for i in form:
                try:
                    payload[i["name"]] = i["value"]
                except:
                    pass
            payload["forcePlaceOrder"] = "Place this duplicate order"
            payload["hasWorkingJavascript"] = "1"
            req = self.client.post("https://www.amazon.com/gp/buy/spc/handlers/static-submit-decoupled.html?ie=UTF8&groupcount=1", headers=self.header, data=payload)
            soup = BeautifulSoup(req.text, 'html.parser')
            url = soup.find('meta')["content"][7:]

        req = self.client.get(url, headers=self.header) 
        soup = BeautifulSoup(req.text, 'html.parser') 
        yorders = soup.find('h4', {'class': "a-alert-heading"}).get_text()
        if yorders == "Order placed, thanks!":
            self.status_signal.emit({"msg": "order is placed!", "status": "normal"})
            return {"success": True}
        else:
            self.status_signal.emit({"msg": "order was not placed", "status": "normal"})
            return { "success": False, "message": "error code 0x153","log" : {}}
    
    def watch_or_buy(self): #either refreshes page until element in stock then it buys it or it buys it directly 
        
        if not self.check_capkey():
            return {"success": False, "message": "wrong captcha key", "log" : {}}
        
        try:
            self.status_signal.emit({"msg": "starting monitor", "status": "normal"})
            while(not self.check_stock()):
                time.sleep(20)
                #breaks when product in stock
                
            self.selogin(self.email, self.password)
            self.load_cookies()
            self.change_location(self.adr) #to remove further problems
            self.delete_cart()
            self.place_to_cart(self.product)
            self.initiate_checkout()
            self.adrid = self.add_address(self.adr, self.response1)
            self.validate_address(self.adrid) 
            self.pid = self.add_payment(self.ccinfo) 
            adrid = self.add_billing(self.adr2) #adding billing address for cc
            return self.checkout()
        except Authexp:
            message = ex.args[0]
            self.status_signal.emit({"msg": message["msg"], "status": "error"})

    def check_capkey(self):
        try:
            self.solver.balance()
        except:
            return False
        else:
            return True


class Stat:

    def emit(self, a):#can be used to implement a way to talk to a api
        print(a["msg"])

adr = {
  "adr1": "2909 Adams Dr",
  "adr2": "",
  "city" : "Melissa",
  "region": "TX",
  "postalcode": "75454",
  "countrycode": "US",
  "adrfullname": "hmed chiboub",
  "phonenm": "(480) 834-9700",
}

ccinfo = {
"cnum": "1234+1234+1234+1234", 
"ccname": "samir+chiboub",
"expy": "2027",
"expm": "08"
}
