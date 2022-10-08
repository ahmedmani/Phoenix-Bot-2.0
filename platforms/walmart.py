from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from server.src.utils.walmart_encryption import walmart_encryption as w_e
import undetected_chromedriver as webdriver
from selenium.webdriver.common.proxy import *
from selenium.webdriver.common.by import By
import urllib3, requests, time, json, sys, re, random, string, os, code
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.ssl_ import create_urllib3_context
from twocaptcha import TwoCaptcha
from server.src.utils.exceptions import Authexp, Internalexp, captchaExp
from server.src.utils.selenium_utils import AnyEc
from bs4 import BeautifulSoup
from selenium.webdriver import ChromeOptions
from supabase import create_client, Client




#supabase vars
url: str = ""
key: str = ""
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



def safe_execute(f):
	def wrapper(*args, **kwargs):
		for _ in range(2):
			try:
				a = f(*args, **kwargs)
			except Exception as ex:
				if type(ex) == captchaExp:
					args[0].handle_captcha()
				continue
			else:
				return a
	return wrapper


class Walmart:

	def __init__(self, status_signal, product, profile, api_key, supabase, userid):
		self.supabase, self.userid = supabase, userid 
		self.status_signal = status_signal
		self.api_key = api_key #2captcha api _key
		self.solver = TwoCaptcha(self.api_key)
		x = ''.join(random.choice(string.digits + string.ascii_uppercase + string.ascii_lowercase) for _ in range(36))
		self.header = {
			"x-o-platform":   "rweb",
			"dnt":    "1",
			"x-o-correlation-id": x,
			"device_profile_ref_id":  ''.join(random.choice(string.digits + string.ascii_uppercase + string.ascii_lowercase) for _ in range(36)),
			"x-latency-trace":    "1",
			"wm_mp":  "true",
			"x-o-market": "us",
			"x-o-platform-version":   "main-347-5e3156",
			"x-o-gql-query":  "",
			"x-apollo-operation-name":    "",
			"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36",
			"x-o-segment":    "oaoh",
			"content-type":   "application/json",
			"accept": "application/json",
			"x-enable-server-timing": "1",
			"x-o-ccm":    "server",
			"wm_qos.correlation_id":  x,
			"origin": "https://www.walmart.com",
			"sec-fetch-site": "same-origin",
			"sec-fetch-mode": "cors",
			"sec-fetch-dest": "empty",
			"referer":    "https://www.walmart.com/",
			"accept-encoding":    "gzip, deflate, br",
			"accept-language":    "en-US,en;q=0.9,fr;q=0.8,ar;q=0.7",}
		self.session = requests.Session()
		self.session.mount('https://www.walmart.com/', CipherAdapter())
		self.product = product 
		self.monitor_delay = 120 #secondes
		self.status_signal.emit({"msg": "Starting", "status": "normal"})
		self.debug = True #if true will solve captchas manually and give you a interactive shell when unhandeled errors occur 
		# self.session.proxies = {"https": "https://localhost:9090"}
		# self.session.verify = False
		self.profile = profile 
		self.profile["postalCode"] = str(self.profile["postalCode"])
		self.profile["phone"] = "({}) {}-{}".format(self.profile["phone"][:3], self.profile["phone"][3:6], self.profile["phone"][6:])

	def watch_or_buy(self):
		if not self.check_capkey():
			return {"success": False, "message": "wrong captcha key", "log" : {}}

		self.login()		
		lineitems = self.get_cart()
		self.add_shipping_adr()
		self.clean_cart(lineitems)
		offer_id, lineitem_id = self.monitor()
		self.atc(offer_id, lineitem_id)
		# pickup_type is either "PICKUP"  # or "SHIPPING" its set automatically
		self.set_shipping()
		card_data, PIE_key_id, PIE_phase = self.get_PIE(self.profile["card_number"])
		card_id = self.add_payment(card_data, PIE_key_id, PIE_phase)
		try:
			contract_id, tenderplan_id, ipurchase_id = self.get_checkout_ids()
		except Internalexp:
			self.status_signal.emit({"msg": "item is no longer in cart. trying again", "status": "normal"})
			self.clean_cart(lineitems)
			offer_id, lineitem_id = self.monitor()
			self.atc(offer_id, lineitem_id)

		self.submit_payment(contract_id, tenderplan_id, card_id)
		return self.submit_order(contract_id, ipurchase_id, card_id)
	
	@safe_execute
	def get_cart(self):
		self.status_signal.emit({"msg": "getting cart details", "status": "normal"})
		b1 = {
		   "query":"query getCart( $cartInput:CartInput! $includePartialFulfillmentSwitching:Boolean! = false $enableAEBadge:Boolean! = false $includeQueueing:Boolean! = false $includeExpressSla:Boolean! = false $enableACCScheduling:Boolean! = false ){cart(input:$cartInput){...CartFragment}}fragment CartFragment on Cart{id checkoutable customer{id isGuest}cartGiftingDetails{isGiftOrder hasGiftEligibleItem isAddOnServiceAdjustmentNeeded isWalmartProtectionPlanPresent isAppleCarePresent}addressMode migrationLineItems{quantity quantityLabel quantityString accessibilityQuantityLabel offerId usItemId productName thumbnailUrl addOnService priceInfo{linePrice{value displayValue}}selectedVariants{name value}}lineItems{id quantity quantityString quantityLabel hasShippingRestriction isPreOrder isGiftEligible isSubstitutionSelected displayAddOnServices createdDateTime discounts{key displayValue displayLabel value terms subType}isWplusEarlyAccess isEventActive eventType selectedAddOnServices{offerId quantity groupType isGiftEligible error{code upstreamErrorCode errorMsg}}bundleComponents{offerId quantity product{name usItemId imageInfo{thumbnailUrl}}}registryId fulfillmentPreference selectedVariants{name value}priceInfo{priceDisplayCodes{showItemPrice priceDisplayCondition finalCostByWeight}itemPrice{...lineItemPriceInfoFragment}wasPrice{...lineItemPriceInfoFragment}unitPrice{...lineItemPriceInfoFragment}linePrice{...lineItemPriceInfoFragment}}product{id name usItemId sponsoredProduct{spQs clickBeacon spTags}sellerDisplayName fulfillmentBadge variants{availabilityStatus}seller{name sellerId}imageInfo{thumbnailUrl}addOnServices{serviceType serviceTitle serviceSubTitle groups{groupType groupTitle assetUrl shortDescription services{displayName selectedDisplayName offerId usItemId currentPrice{priceString price}serviceMetaData giftEligible}}}itemType offerId sellerId sellerName hasSellerBadge orderLimit orderMinLimit weightUnit weightIncrement salesUnit salesUnitType sellerType isAlcohol fulfillmentType fulfillmentSpeed fulfillmentTitle classType rhPath availabilityStatus brand category{categoryPath}departmentName configuration snapEligible preOrder{isPreOrder}badges @include(if:$enableAEBadge){...BadgesFragment}shippingOption{shipPrice{priceString}}}registryInfo{registryId registryType}wirelessPlan{planId mobileNumber postPaidPlan{...postpaidPlanDetailsFragment}}fulfillmentSourcingDetails{currentSelection requestedSelection fulfillmentBadge}availableQty expiresAt @include(if:$includeQueueing) showExpirationTimer @include(if:$includeQueueing)}fulfillment{intent accessPoint{...accessPointCartFragment}reservation{...reservationFragment}storeId displayStoreSnackBarMessage homepageBookslotDetails{title subTitle expiryText expiryTime slotExpiryText}deliveryAddress{addressLineOne addressLineTwo city state postalCode firstName lastName id phone}fulfillmentItemGroups{...on FCGroup{__typename defaultMode collapsedItemIds startDate endDate checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...priceTotalFields}}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}shippingOptions{__typename itemIds availableShippingOptions{__typename id shippingMethod deliveryDate price{__typename displayValue value}label{prefix suffix}isSelected isDefault slaTier}}hasMadeShippingChanges slaGroups{__typename label deliveryDate sellerGroups{__typename id name isProSeller type catalogSellerId shipOptionGroup{__typename deliveryPrice{__typename displayValue value}itemIds shipMethod}}warningLabel}}...on SCGroup{__typename defaultMode collapsedItemIds checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...priceTotalFields}}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}itemGroups{__typename label itemIds accessPoint{...accessPointCartFragment}}accessPoint{...accessPointCartFragment}reservation{...reservationFragment}}...on DigitalDeliveryGroup{__typename defaultMode collapsedItemIds checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...priceTotalFields}}itemGroups{__typename label itemIds accessPoint{...accessPointCartFragment}}}...on Unscheduled{__typename defaultMode collapsedItemIds checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...priceTotalFields}}itemGroups{__typename label itemIds accessPoint{...accessPointCartFragment}}accessPoint{...accessPointCartFragment}reservation{...reservationFragment}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}isSpecialEvent @include(if:$enableAEBadge)}...on AutoCareCenter{__typename defaultMode collapsedItemIds startDate endDate accBasketType checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...priceTotalFields}}itemGroups{__typename label itemIds accessPoint{...accessPointCartFragment}}accFulfillmentGroups @include(if:$enableACCScheduling){collapsedItemIds itemGroupType reservation{...reservationFragment}suggestedSlotAvailability{...suggestedSlotAvailabilityFragment}itemGroups{__typename label itemIds}}accessPoint{...accessPointCartFragment}reservation{...reservationFragment}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}}}suggestedSlotAvailability{...suggestedSlotAvailabilityFragment}}priceDetails{subTotal{...priceTotalFields}fees{...priceTotalFields}taxTotal{...priceTotalFields}grandTotal{...priceTotalFields}belowMinimumFee{...priceTotalFields}minimumThreshold{value displayValue}ebtSnapMaxEligible{displayValue value}balanceToMinimumThreshold{value displayValue}totalItemQuantity}affirm{isMixedPromotionCart message{description termsUrl imageUrl monthlyPayment termLength isZeroAPR}nonAffirmGroup{...nonAffirmGroupFields}affirmGroups{...on AffirmItemGroup{__typename message{description termsUrl imageUrl monthlyPayment termLength isZeroAPR}flags{type displayLabel}name label itemCount itemIds defaultMode}}}checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}checkoutableWarnings{code itemIds}operationalErrors{offerId itemId requestedQuantity adjustedQuantity code upstreamErrorCode}cartCustomerContext{...cartCustomerContextFragment}}fragment postpaidPlanDetailsFragment on PostPaidPlan{espOrderSummaryId espOrderId espOrderLineId warpOrderId warpSessionId isPostpaidExpired devicePayment{...postpaidPlanPriceFragment}devicePlan{price{...postpaidPlanPriceFragment}frequency duration annualPercentageRate}deviceDataPlan{...deviceDataPlanFragment}}fragment deviceDataPlanFragment on DeviceDataPlan{carrierName planType expiryTime activationFee{...postpaidPlanPriceFragment}planDetails{price{...postpaidPlanPriceFragment}frequency name}agreements{...agreementFragment}}fragment postpaidPlanPriceFragment on PriceDetailRow{key label displayValue value strikeOutDisplayValue strikeOutValue info{title message}}fragment agreementFragment on CarrierAgreement{name type format value docTitle label}fragment priceTotalFields on PriceDetailRow{label displayValue value key strikeOutDisplayValue strikeOutValue}fragment lineItemPriceInfoFragment on Price{displayValue value}fragment accessPointCartFragment on AccessPoint{id assortmentStoreId name nodeAccessType accessType fulfillmentType fulfillmentOption displayName timeZone bagFeeValue isActive address{addressLineOne addressLineTwo city postalCode state phone}}fragment suggestedSlotAvailabilityFragment on SuggestedSlotAvailability{isPickupAvailable isDeliveryAvailable nextPickupSlot{startTime endTime slaInMins}nextDeliverySlot{startTime endTime slaInMins}nextUnscheduledPickupSlot{startTime endTime slaInMins}nextSlot{__typename...on RegularSlot{fulfillmentOption fulfillmentType startTime}...on DynamicExpressSlot{fulfillmentOption fulfillmentType startTime slaInMins sla{value displayValue}}...on UnscheduledSlot{fulfillmentOption fulfillmentType startTime unscheduledHoldInDays}...on InHomeSlot{fulfillmentOption fulfillmentType startTime}}}fragment reservationFragment on Reservation{expiryTime isUnscheduled expired showSlotExpiredError reservedSlot{__typename...on RegularSlot{id price{total{value displayValue}expressFee{value displayValue}baseFee{value displayValue}memberBaseFee{value displayValue}}nodeAccessType accessPointId fulfillmentOption startTime fulfillmentType slotMetadata endTime available supportedTimeZone isAlcoholRestricted}...on DynamicExpressSlot{id price{total{value displayValue}expressFee{value displayValue}baseFee{value displayValue}memberBaseFee{value displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata available sla @include(if:$includeExpressSla){value displayValue}slaInMins maxItemAllowed supportedTimeZone isAlcoholRestricted}...on UnscheduledSlot{price{total{value displayValue}expressFee{value displayValue}baseFee{value displayValue}memberBaseFee{value displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata unscheduledHoldInDays supportedTimeZone}...on InHomeSlot{id price{total{value displayValue}expressFee{value displayValue}baseFee{value displayValue}memberBaseFee{value displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata endTime available supportedTimeZone isAlcoholRestricted}}}fragment nonAffirmGroupFields on NonAffirmGroup{label itemCount itemIds collapsedItemIds}fragment cartCustomerContextFragment on CartCustomerContext{isMembershipOptedIn isEligibleForFreeTrial membershipData{isActiveMember isPaidMember}paymentData{hasCreditCard hasCapOne hasDSCard hasEBT isCapOneLinked showCapOneBanner}}fragment BadgesFragment on UnifiedBadge{flags{__typename...on BaseBadge{id text key query}...on PreviouslyPurchasedBadge{id text key lastBoughtOn numBought criteria{name value}}}labels{__typename...on BaseBadge{id text key}...on PreviouslyPurchasedBadge{id text key lastBoughtOn numBought}}tags{__typename...on BaseBadge{id text key}...on PreviouslyPurchasedBadge{id text key}}}",
		   "variables":{
			  "cartInput":{
				 "cartId": None,
				 "forceRefresh":False
			  },
			  "includePartialFulfillmentSwitching":True,
			  "enableAEBadge":True,
			  "includeQueueing":True,
			  "includeExpressSla":True,
			  "enableACCScheduling":False
		   }}
		self.header["x-o-gql-query"] = "query getCart"
		self.header["x-apollo-operation-name"] = "getCart"
		
		r = self.session.post("https://www.walmart.com/orchestra/cartxo/graphql", headers=self.header, data=json.dumps(b1))
		if self.is_captcha(r.text):
			raise captchaExp()
		if r.status_code == 200:
			self.status_signal.emit({"msg": "got cart details", "status": "normal"})
			data = json.loads(r.text)
			# print("is cart checkoutable?:" , data["data"]["cart"]["checkoutable"])        
			self.cart_id = data["data"]["cart"]["id"]
			lineitems = data["data"]["cart"]["lineItems"]
			return lineitems
		else:
			self.status_signal.emit({"msg": "error getting cart details", "status": "error"})
			raise Internalexp()
	
	@safe_execute
	def clean_cart(self, lineitems):     
		self.status_signal.emit({"msg": "clearing cart", "status": "normal"})
		b2 = {
			"query":"mutation updateItems( $input:UpdateItemsInput! $detailed:Boolean! = false $includePartialFulfillmentSwitching:Boolean! = false $enableAEBadge:Boolean! = false $includeQueueing:Boolean! = false $includeExpressSla:Boolean! = false $enableACCScheduling:Boolean! = false ){updateItems(input:$input){id checkoutable customer{id isGuest}cartGiftingDetails{isGiftOrder hasGiftEligibleItem isAddOnServiceAdjustmentNeeded isWalmartProtectionPlanPresent isAppleCarePresent}addressMode migrationLineItems @include(if:$detailed){quantity quantityLabel quantityString accessibilityQuantityLabel offerId usItemId productName thumbnailUrl addOnService priceInfo{linePrice{value displayValue}}selectedVariants{name value}}lineItems{id quantity quantityString quantityLabel isGiftEligible createdDateTime displayAddOnServices isWplusEarlyAccess isEventActive eventType isSubstitutionSelected discounts{key displayValue displayLabel value terms subType}selectedAddOnServices{offerId quantity groupType isGiftEligible error{code upstreamErrorCode errorMsg}}isPreOrder @include(if:$detailed) bundleComponents{offerId quantity product @include(if:$detailed){name usItemId imageInfo{thumbnailUrl}}}registryId registryInfo{registryId registryType}fulfillmentPreference selectedVariants @include(if:$detailed){name value}priceInfo{priceDisplayCodes{showItemPrice priceDisplayCondition finalCostByWeight}itemPrice{...merge_lineItemPriceInfoFragment}wasPrice{...merge_lineItemPriceInfoFragment}unitPrice{...merge_lineItemPriceInfoFragment}linePrice{...merge_lineItemPriceInfoFragment}}product{name @include(if:$detailed) usItemId addOnServices @include(if:$detailed){serviceType serviceTitle serviceSubTitle groups{groupType groupTitle assetUrl shortDescription services{displayName selectedDisplayName offerId currentPrice{priceString price}serviceMetaData giftEligible}}}imageInfo @include(if:$detailed){thumbnailUrl}itemType offerId sellerId sellerName hasSellerBadge @include(if:$detailed) orderLimit orderMinLimit weightUnit @include(if:$detailed) weightIncrement @include(if:$detailed) salesUnit salesUnitType sellerType @include(if:$detailed) isAlcohol @include(if:$detailed) fulfillmentType fulfillmentSpeed @include(if:$detailed) fulfillmentTitle @include(if:$detailed) classType @include(if:$detailed) rhPath @include(if:$detailed) availabilityStatus @include(if:$detailed) brand @include(if:$detailed) category @include(if:$detailed){categoryPath}departmentName @include(if:$detailed) configuration @include(if:$detailed) snapEligible @include(if:$detailed) preOrder @include(if:$detailed){isPreOrder}badges @include(if:$enableAEBadge){...BadgesFragment}shippingOption{shipPrice{priceString}}}wirelessPlan @include(if:$detailed){planId mobileNumber postPaidPlan{...merge_postpaidPlanDetailsFragment}}fulfillmentSourcingDetails @include(if:$detailed){currentSelection requestedSelection fulfillmentBadge}expiresAt @include(if:$includeQueueing) showExpirationTimer @include(if:$includeQueueing)}fulfillment{intent @include(if:$detailed) accessPoint @include(if:$detailed){...merge_accessPointFragment}reservation @include(if:$detailed){...mergeCart_reservationFragment}storeId displayStoreSnackBarMessage homepageBookslotDetails @include(if:$detailed){title subTitle expiryText expiryTime slotExpiryText}deliveryAddress @include(if:$detailed){addressLineOne addressLineTwo city state postalCode firstName lastName id}fulfillmentItemGroups @include(if:$detailed){...on FCGroup{__typename defaultMode collapsedItemIds startDate endDate checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...merge_priceTotalFields}}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}shippingOptions{__typename itemIds availableShippingOptions{__typename id shippingMethod deliveryDate price{__typename displayValue value}label{prefix suffix}isSelected isDefault slaTier}}hasMadeShippingChanges slaGroups{__typename label sellerGroups{__typename id name isProSeller type catalogSellerId shipOptionGroup{__typename deliveryPrice{__typename displayValue value}itemIds shipMethod @include(if:$detailed)}}warningLabel}}...on SCGroup{__typename defaultMode collapsedItemIds checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...merge_priceTotalFields}}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}itemGroups{__typename label itemIds}accessPoint{...merge_accessPointFragment}reservation{...mergeCart_reservationFragment}}...on DigitalDeliveryGroup{__typename defaultMode collapsedItemIds checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...merge_priceTotalFields}}itemGroups{__typename label itemIds}}...on Unscheduled{__typename defaultMode collapsedItemIds checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...merge_priceTotalFields}}itemGroups{__typename label itemIds}accessPoint{...merge_accessPointFragment}reservation{...mergeCart_reservationFragment}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}isSpecialEvent @include(if:$enableAEBadge)}...on AutoCareCenter{__typename defaultMode collapsedItemIds startDate endDate accBasketType checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...merge_priceTotalFields}}itemGroups{__typename label itemIds}accFulfillmentGroups @include(if:$enableACCScheduling){collapsedItemIds itemGroupType reservation{...mergeCart_reservationFragment}suggestedSlotAvailability{...mergeCart_suggestedSlotAvailabilityFragment}itemGroups{__typename label itemIds}}accessPoint{...merge_accessPointFragment}reservation{...mergeCart_reservationFragment}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}}}suggestedSlotAvailability @include(if:$detailed){...mergeCart_suggestedSlotAvailabilityFragment}}priceDetails{subTotal{value displayValue label @include(if:$detailed) key @include(if:$detailed) strikeOutDisplayValue @include(if:$detailed) strikeOutValue @include(if:$detailed)}fees @include(if:$detailed){...merge_priceTotalFields}taxTotal @include(if:$detailed){...merge_priceTotalFields}grandTotal @include(if:$detailed){...merge_priceTotalFields}belowMinimumFee @include(if:$detailed){...merge_priceTotalFields}minimumThreshold @include(if:$detailed){value displayValue}ebtSnapMaxEligible @include(if:$detailed){displayValue value}balanceToMinimumThreshold @include(if:$detailed){value displayValue}}affirm @include(if:$detailed){isMixedPromotionCart message{description termsUrl imageUrl monthlyPayment termLength isZeroAPR}nonAffirmGroup{...nonAffirmGroupFields}affirmGroups{...on AffirmItemGroup{__typename message{description termsUrl imageUrl monthlyPayment termLength isZeroAPR}flags{type displayLabel}name label itemCount itemIds defaultMode}}}checkoutableErrors @include(if:$detailed){code shouldDisableCheckout itemIds}checkoutableWarnings @include(if:$detailed){code itemIds}operationalErrors{offerId itemId requestedQuantity adjustedQuantity code upstreamErrorCode}cartCustomerContext{...cartCustomerContextFragment}}}fragment merge_postpaidPlanDetailsFragment on PostPaidPlan{espOrderSummaryId espOrderId espOrderLineId warpOrderId warpSessionId devicePayment{...merge_postpaidPlanPriceFragment}devicePlan{price{...merge_postpaidPlanPriceFragment}frequency duration annualPercentageRate}deviceDataPlan{...merge_deviceDataPlanFragment}}fragment merge_deviceDataPlanFragment on DeviceDataPlan{carrierName planType expiryTime activationFee{...merge_postpaidPlanPriceFragment}planDetails{price{...merge_postpaidPlanPriceFragment}frequency name}agreements{...merge_agreementFragment}}fragment merge_postpaidPlanPriceFragment on PriceDetailRow{key label displayValue value strikeOutDisplayValue strikeOutValue info{title message}}fragment merge_agreementFragment on CarrierAgreement{name type format value docTitle label}fragment merge_priceTotalFields on PriceDetailRow{label displayValue value key strikeOutDisplayValue strikeOutValue}fragment merge_lineItemPriceInfoFragment on Price{displayValue value}fragment merge_accessPointFragment on AccessPoint{id assortmentStoreId name nodeAccessType fulfillmentType fulfillmentOption displayName timeZone address{addressLineOne addressLineTwo city postalCode state phone}}fragment mergeCart_suggestedSlotAvailabilityFragment on SuggestedSlotAvailability{isPickupAvailable isDeliveryAvailable nextPickupSlot{startTime endTime slaInMins}nextDeliverySlot{startTime endTime slaInMins}nextUnscheduledPickupSlot{startTime endTime slaInMins}nextSlot{__typename...on RegularSlot{fulfillmentOption fulfillmentType startTime}...on DynamicExpressSlot{fulfillmentOption fulfillmentType startTime slaInMins}...on UnscheduledSlot{fulfillmentOption fulfillmentType startTime unscheduledHoldInDays}...on InHomeSlot{fulfillmentOption fulfillmentType startTime}}}fragment mergeCart_reservationFragment on Reservation{expiryTime isUnscheduled expired showSlotExpiredError reservedSlot{__typename...on RegularSlot{id price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata endTime available supportedTimeZone isAlcoholRestricted}...on DynamicExpressSlot{id price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata available sla @include(if:$includeExpressSla){value displayValue}slaInMins maxItemAllowed supportedTimeZone isAlcoholRestricted}...on UnscheduledSlot{price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata unscheduledHoldInDays supportedTimeZone}...on InHomeSlot{id price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata endTime available supportedTimeZone isAlcoholRestricted}}}fragment nonAffirmGroupFields on NonAffirmGroup{label itemCount itemIds collapsedItemIds}fragment cartCustomerContextFragment on CartCustomerContext{isMembershipOptedIn isEligibleForFreeTrial membershipData{isActiveMember isPaidMember}paymentData{hasCreditCard hasCapOne hasDSCard hasEBT isCapOneLinked showCapOneBanner}}fragment BadgesFragment on UnifiedBadge{flags{__typename...on BaseBadge{id text key query}...on PreviouslyPurchasedBadge{id text key lastBoughtOn numBought criteria{name value}}}labels{__typename...on BaseBadge{id text key}...on PreviouslyPurchasedBadge{id text key lastBoughtOn numBought}}tags{__typename...on BaseBadge{id text key}...on PreviouslyPurchasedBadge{id text key}}}",
			"variables":{
			   "input":{
				  "cartId": self.cart_id,
				  "items": [{"offerId": i["product"]["offerId"],"quantity": 0} for i in lineitems]
			   },
			   "detailed":True,
			   "includePartialFulfillmentSwitching":True,
			   "enableAEBadge":True,
			   "includeQueueing":True,
			   "includeExpressSla":True,
			   "enableACCScheduling":False
			}
		}
		self.header["x-apollo-operation-name"] = "updateItems"
		self.header["x-o-gql-query"] =  "query updateItems"

		r = self.session.post("https://www.walmart.com/orchestra/cartxo/graphql", headers=self.header, data=json.dumps(b2))
		if self.is_captcha(r.text):
			raise captchaExp()
		if r.status_code == 200:
			self.status_signal.emit({"msg": "cart is cleared", "status": "normal"})
		else:
			self.status_signal.emit({"msg": "error clearing cart", "status": "error"})
			raise Internalexp()

	@safe_execute
	def monitor(self):
		while(True):
			self.status_signal.emit({"msg": "Loading initial cookies", "status": "normal"})
			self.load_cookies() #already called from login no need to recall it
			# print(self.session.cookies.get_dict())
			r = self.session.get(self.product, headers=self.header)  
			# print(r.text)
			if self.is_captcha(r.text):
				raise captchaExp()

			if r.status_code == 200:       
				self.status_signal.emit({"msg": "Loading Product Page", "status": "normal"})
				if "add to cart" in r.text.lower():
					self.status_signal.emit({"msg": "Product Page Loaded", "status": "normal"})
					soup = BeautifulSoup(r.text, 'html.parser')
					data = json.loads(soup.find('script', {'id': '__NEXT_DATA__'}).contents[0])
					product = data["props"]["pageProps"]["initialData"]["data"]["product"]
					lineitem_id = product["id"]
					offer_id = product["offerId"]
					return offer_id, lineitem_id

				self.status_signal.emit({"msg": "Waiting For Restock", "status": "normal"})
				time.sleep(self.monitor_delay)
				
			else:
				self.status_signal.emit({"msg": "Product Not Found", "status": "normal"})
				if self.debug:
					code.interact(local=locals())
		   
	@safe_execute
	def atc(self, offer_id, lineitem_id):
		self.status_signal.emit({"msg": "Adding To Cart", "status": "normal"})
		b2 = {
			"query": "mutation updateItems( $input:UpdateItemsInput! $detailed:Boolean! = false $includePartialFulfillmentSwitching:Boolean! = false $enableAEBadge:Boolean! = false $includeQueueing:Boolean! = false $includeExpressSla:Boolean! = false $enableACCScheduling:Boolean! = false ){updateItems(input:$input){id checkoutable customer{id isGuest}cartGiftingDetails{isGiftOrder hasGiftEligibleItem isAddOnServiceAdjustmentNeeded isWalmartProtectionPlanPresent isAppleCarePresent}addressMode migrationLineItems @include(if:$detailed){quantity quantityLabel quantityString accessibilityQuantityLabel offerId usItemId productName thumbnailUrl addOnService priceInfo{linePrice{value displayValue}}selectedVariants{name value}}lineItems{id quantity quantityString quantityLabel isGiftEligible createdDateTime displayAddOnServices isWplusEarlyAccess isEventActive eventType isSubstitutionSelected discounts{key displayValue displayLabel value terms subType}selectedAddOnServices{offerId quantity groupType isGiftEligible error{code upstreamErrorCode errorMsg}}isPreOrder @include(if:$detailed) bundleComponents{offerId quantity product @include(if:$detailed){name usItemId imageInfo{thumbnailUrl}}}registryId registryInfo{registryId registryType}fulfillmentPreference selectedVariants @include(if:$detailed){name value}priceInfo{priceDisplayCodes{showItemPrice priceDisplayCondition finalCostByWeight}itemPrice{...merge_lineItemPriceInfoFragment}wasPrice{...merge_lineItemPriceInfoFragment}unitPrice{...merge_lineItemPriceInfoFragment}linePrice{...merge_lineItemPriceInfoFragment}}product{name @include(if:$detailed) usItemId addOnServices @include(if:$detailed){serviceType serviceTitle serviceSubTitle groups{groupType groupTitle assetUrl shortDescription services{displayName selectedDisplayName offerId currentPrice{priceString price}serviceMetaData giftEligible}}}imageInfo @include(if:$detailed){thumbnailUrl}itemType offerId sellerId sellerName hasSellerBadge @include(if:$detailed) orderLimit orderMinLimit weightUnit @include(if:$detailed) weightIncrement @include(if:$detailed) salesUnit salesUnitType sellerType @include(if:$detailed) isAlcohol @include(if:$detailed) fulfillmentType fulfillmentSpeed @include(if:$detailed) fulfillmentTitle @include(if:$detailed) classType @include(if:$detailed) rhPath @include(if:$detailed) availabilityStatus @include(if:$detailed) brand @include(if:$detailed) category @include(if:$detailed){categoryPath}departmentName @include(if:$detailed) configuration @include(if:$detailed) snapEligible @include(if:$detailed) preOrder @include(if:$detailed){isPreOrder}badges @include(if:$enableAEBadge){...BadgesFragment}shippingOption{shipPrice{priceString}}}wirelessPlan @include(if:$detailed){planId mobileNumber postPaidPlan{...merge_postpaidPlanDetailsFragment}}fulfillmentSourcingDetails @include(if:$detailed){currentSelection requestedSelection fulfillmentBadge}expiresAt @include(if:$includeQueueing) showExpirationTimer @include(if:$includeQueueing)}fulfillment{intent @include(if:$detailed) accessPoint @include(if:$detailed){...merge_accessPointFragment}reservation @include(if:$detailed){...mergeCart_reservationFragment}storeId displayStoreSnackBarMessage homepageBookslotDetails @include(if:$detailed){title subTitle expiryText expiryTime slotExpiryText}deliveryAddress @include(if:$detailed){addressLineOne addressLineTwo city state postalCode firstName lastName id}fulfillmentItemGroups @include(if:$detailed){...on FCGroup{__typename defaultMode collapsedItemIds startDate endDate checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...merge_priceTotalFields}}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}shippingOptions{__typename itemIds availableShippingOptions{__typename id shippingMethod deliveryDate price{__typename displayValue value}label{prefix suffix}isSelected isDefault slaTier}}hasMadeShippingChanges slaGroups{__typename label sellerGroups{__typename id name isProSeller type catalogSellerId shipOptionGroup{__typename deliveryPrice{__typename displayValue value}itemIds shipMethod @include(if:$detailed)}}warningLabel}}...on SCGroup{__typename defaultMode collapsedItemIds checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...merge_priceTotalFields}}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}itemGroups{__typename label itemIds}accessPoint{...merge_accessPointFragment}reservation{...mergeCart_reservationFragment}}...on DigitalDeliveryGroup{__typename defaultMode collapsedItemIds checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...merge_priceTotalFields}}itemGroups{__typename label itemIds}}...on Unscheduled{__typename defaultMode collapsedItemIds checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...merge_priceTotalFields}}itemGroups{__typename label itemIds}accessPoint{...merge_accessPointFragment}reservation{...mergeCart_reservationFragment}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}isSpecialEvent @include(if:$enableAEBadge)}...on AutoCareCenter{__typename defaultMode collapsedItemIds startDate endDate accBasketType checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...merge_priceTotalFields}}itemGroups{__typename label itemIds}accFulfillmentGroups @include(if:$enableACCScheduling){collapsedItemIds itemGroupType reservation{...mergeCart_reservationFragment}suggestedSlotAvailability{...mergeCart_suggestedSlotAvailabilityFragment}itemGroups{__typename label itemIds}}accessPoint{...merge_accessPointFragment}reservation{...mergeCart_reservationFragment}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}}}suggestedSlotAvailability @include(if:$detailed){...mergeCart_suggestedSlotAvailabilityFragment}}priceDetails{subTotal{value displayValue label @include(if:$detailed) key @include(if:$detailed) strikeOutDisplayValue @include(if:$detailed) strikeOutValue @include(if:$detailed)}fees @include(if:$detailed){...merge_priceTotalFields}taxTotal @include(if:$detailed){...merge_priceTotalFields}grandTotal @include(if:$detailed){...merge_priceTotalFields}belowMinimumFee @include(if:$detailed){...merge_priceTotalFields}minimumThreshold @include(if:$detailed){value displayValue}ebtSnapMaxEligible @include(if:$detailed){displayValue value}balanceToMinimumThreshold @include(if:$detailed){value displayValue}}affirm @include(if:$detailed){isMixedPromotionCart message{description termsUrl imageUrl monthlyPayment termLength isZeroAPR}nonAffirmGroup{...nonAffirmGroupFields}affirmGroups{...on AffirmItemGroup{__typename message{description termsUrl imageUrl monthlyPayment termLength isZeroAPR}flags{type displayLabel}name label itemCount itemIds defaultMode}}}checkoutableErrors @include(if:$detailed){code shouldDisableCheckout itemIds}checkoutableWarnings @include(if:$detailed){code itemIds}operationalErrors{offerId itemId requestedQuantity adjustedQuantity code upstreamErrorCode}cartCustomerContext{...cartCustomerContextFragment}}}fragment merge_postpaidPlanDetailsFragment on PostPaidPlan{espOrderSummaryId espOrderId espOrderLineId warpOrderId warpSessionId devicePayment{...merge_postpaidPlanPriceFragment}devicePlan{price{...merge_postpaidPlanPriceFragment}frequency duration annualPercentageRate}deviceDataPlan{...merge_deviceDataPlanFragment}}fragment merge_deviceDataPlanFragment on DeviceDataPlan{carrierName planType expiryTime activationFee{...merge_postpaidPlanPriceFragment}planDetails{price{...merge_postpaidPlanPriceFragment}frequency name}agreements{...merge_agreementFragment}}fragment merge_postpaidPlanPriceFragment on PriceDetailRow{key label displayValue value strikeOutDisplayValue strikeOutValue info{title message}}fragment merge_agreementFragment on CarrierAgreement{name type format value docTitle label}fragment merge_priceTotalFields on PriceDetailRow{label displayValue value key strikeOutDisplayValue strikeOutValue}fragment merge_lineItemPriceInfoFragment on Price{displayValue value}fragment merge_accessPointFragment on AccessPoint{id assortmentStoreId name nodeAccessType fulfillmentType fulfillmentOption displayName timeZone address{addressLineOne addressLineTwo city postalCode state phone}}fragment mergeCart_suggestedSlotAvailabilityFragment on SuggestedSlotAvailability{isPickupAvailable isDeliveryAvailable nextPickupSlot{startTime endTime slaInMins}nextDeliverySlot{startTime endTime slaInMins}nextUnscheduledPickupSlot{startTime endTime slaInMins}nextSlot{__typename...on RegularSlot{fulfillmentOption fulfillmentType startTime}...on DynamicExpressSlot{fulfillmentOption fulfillmentType startTime slaInMins}...on UnscheduledSlot{fulfillmentOption fulfillmentType startTime unscheduledHoldInDays}...on InHomeSlot{fulfillmentOption fulfillmentType startTime}}}fragment mergeCart_reservationFragment on Reservation{expiryTime isUnscheduled expired showSlotExpiredError reservedSlot{__typename...on RegularSlot{id price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata endTime available supportedTimeZone isAlcoholRestricted}...on DynamicExpressSlot{id price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata available sla @include(if:$includeExpressSla){value displayValue}slaInMins maxItemAllowed supportedTimeZone isAlcoholRestricted}...on UnscheduledSlot{price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata unscheduledHoldInDays supportedTimeZone}...on InHomeSlot{id price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata endTime available supportedTimeZone isAlcoholRestricted}}}fragment nonAffirmGroupFields on NonAffirmGroup{label itemCount itemIds collapsedItemIds}fragment cartCustomerContextFragment on CartCustomerContext{isMembershipOptedIn isEligibleForFreeTrial membershipData{isActiveMember isPaidMember}paymentData{hasCreditCard hasCapOne hasDSCard hasEBT isCapOneLinked showCapOneBanner}}fragment BadgesFragment on UnifiedBadge{flags{__typename...on BaseBadge{id text key query}...on PreviouslyPurchasedBadge{id text key lastBoughtOn numBought criteria{name value}}}labels{__typename...on BaseBadge{id text key}...on PreviouslyPurchasedBadge{id text key lastBoughtOn numBought}}tags{__typename...on BaseBadge{id text key}...on PreviouslyPurchasedBadge{id text key}}}",
			"variables": {
				"detailed": False,
				"enableACCScheduling": False,
				"enableAEBadge": True,
				"includeExpressSla": True,
				"includePartialFulfillmentSwitching": True,
				"includeQueueing": True,
				"input": {
					"cartId": self.cart_id,
					"isGiftOrder": None,
					"items": [
						{
							"additionalInfo": {
								"addOnServices": []
							},
							"lineItemId": lineitem_id,
							"offerId": offer_id,
							"quantity": 1
						}
					]
				}
			}
		}
		self.header["x-apollo-operation-name"] = "updateItems"
		self.header["x-o-gql-query"] = "mutation updateItems"
		r = self.session.post("https://www.walmart.com/orchestra/cartxo/graphql", headers=self.header, data=json.dumps(b2))
		data = json.loads(r.text)
		if self.is_captcha(r.text):
			raise captchaExp()
		if "errors" not in data.keys() and r.status_code == 200:
			self.status_signal.emit({"msg": "Added To Cart", "status": "carted"})
			return True

		else:
			self.status_signal.emit({"msg": "Error Adding To Cart", "status": "error"})
			raise Internalexp()

	@safe_execute
	def get_slots(self, pickup_type): 
		b = {
		   "query":"query getSlots( $cartId:ID! $fulfillmentOption:FulfillmentOption! $cartFulfillmentOption:CartFulfillmentOption $isGuest:Boolean! $isExpressSla:Boolean! ){slots( input:{cartId:$cartId fulfillmentOption:$fulfillmentOption cartFulfillmentOption:$cartFulfillmentOption}){guestReservationExtensionMessage scheduledEnabled slotDays{day hasAvailableSlots hasUnreleasedSlots hasInHomeSlot eachDaySlots{__typename...on RegularSlot{accessPointId fulfillmentType slotMetadata startTime id available endTime isAlcoholRestricted isVulnerable slotExpiryTime slotIndicator price{baseFee{displayValue}expressFee{displayValue}total{value displayValue}memberBaseFee{displayValue}optedInTotal @skip(if:$isGuest){displayValue}}isPrimary}...on DynamicExpressSlot{accessPointId fulfillmentType slotMetadata startTime id available endTime isAlcoholRestricted isVulnerable slotExpiryTime slotIndicator isSelectable maxItemAllowed slaInMins price{baseFee{displayValue}expressFee{displayValue}total{value displayValue}memberBaseFee{displayValue}optedInTotal @skip(if:$isGuest){displayValue}}isPrimary sla @include(if:$isExpressSla){displayValue}}...on InHomeSlot{accessPointId fulfillmentType slotMetadata startTime id available endTime isAlcoholRestricted isVulnerable slotExpiryTime slotIndicator price{baseFee{displayValue}expressFee{displayValue}total{value displayValue}memberBaseFee{displayValue}optedInTotal @skip(if:$isGuest){displayValue}}isPrimary}}}accessPoints{id assortmentStoreId nodeAccessType displayName fulfillmentOption cartFulfillmentOption fulfillmentType timeZone address{addressLineOne addressLineTwo city state postalCode state}isExpressEligible}nextAvailableSlots{deliverySlot{__typename...nextRegularSlot...nextExpressSlot...nextInHomeSlot}pickupSlot{__typename...nextRegularSlot...nextExpressSlot...nextInHomeSlot}unscheduledPickupSlot{unscheduledHoldInDays slotMetadata startTime price{total{displayValue}}}earliestPickupSlotTime}hasFreeOfCostDeliverySlotsForWPlusUsers cartCustomerContext @skip(if:$isGuest){isEligibleForFreeTrial isMembershipOptedIn membershipData{isActiveMember}paymentData{hasCreditCard}}customerLocationInfo{isDefaultStore}}}fragment nextRegularSlot on RegularSlot{id startTime endTime fulfillmentType slotMetadata}fragment nextInHomeSlot on InHomeSlot{id startTime endTime fulfillmentType slotMetadata}fragment nextExpressSlot on DynamicExpressSlot{id startTime endTime fulfillmentType slotMetadata slaInMins}",
		   "variables":{
			  "cartId": self.cart_id,
			  "fulfillmentOption":pickup_type,
			  "cartFulfillmentOption":pickup_type,
			  "isGuest":False,
			  "isExpressSla":True
		   }
		}      
		self.header["x-o-gql-query"] = "query getSlots"
		self.header["x-apollo-operation-name"] = "getSlots"

		r = self.session.post("https://www.walmart.com/orchestra/home/graphql", headers=self.header, data=json.dumps(b))
		data = json.loads(r.text)
		if self.is_captcha(r.text):
			raise captchaExp()
		return data["data"]["slots"]["slotDays"]

	@safe_execute
	def add_shipping_adr(self): #adds a shipping address and changes to that location
		b = {
		   "query":"mutation CreateDeliveryAddress($input:AccountAddressesInput!){createAccountAddress(input:$input){...DeliveryAddressMutationResponse}}fragment DeliveryAddressMutationResponse on MutateAccountAddressResponse{...AddressMutationResponse newAddress{id accessPoint{...AccessPoint}...BaseAddressResponse}}fragment AccessPoint on AccessPointRovr{id assortmentStoreId fulfillmentType accountFulfillmentOption accountAccessType}fragment AddressMutationResponse on MutateAccountAddressResponse{errors{code}enteredAddress{...BasicAddress}suggestedAddresses{...BasicAddress sealedAddress}newAddress{id...BaseAddressResponse}allowAvsOverride}fragment BasicAddress on AccountAddressBase{addressLineOne addressLineTwo city state postalCode}fragment BaseAddressResponse on AccountAddress{...BasicAddress firstName lastName phone isDefault deliveryInstructions serviceStatus capabilities allowEditOrRemove}",
		   "variables":{
			  "input":{
				 "address":{
					"addressLineOne":self.profile["addressLineOne"],
					"addressLineTwo":self.profile["addressLineTwo"],
					"city": self.profile["city"],
					"postalCode": self.profile["postalCode"],
					"state":self.profile["state"],
					"addressType":None,
					"businessName":None,
					"isApoFpo":None,
					"isLoadingDockAvailable":None,
					"isPoBox":None,
					"sealedAddress":None
				 },
				 "firstName": self.profile["firstName"],
				 "lastName": self.profile["lastName"],
				 "deliveryInstructions":None,
				 "displayLabel":None,
				 "isDefault":False,
				 "phone": self.profile["phone"],
				 "overrideAvs":False
			  }
		   }
		}
		self.header["x-apollo-operation-name"] = "CreateDeliveryAddress" 
		self.header["x-o-gql-query"] = "mutation CreateDeliveryAddress" 
		self.status_signal.emit({"msg": "adding Shipping Method", "status": "normal"})


		r = self.session.post("https://www.walmart.com/orchestra/home/graphql", data=json.dumps(b), headers=self.header)
		if self.is_captcha(r.text):
			raise captchaExp()
		else:
			data = json.loads(r.text)
			try:    
				errmsg = data["errors"][0]["message"] 
			except:
				pass
			else:
				self.status_signal.emit({"msg": "Error Adding Shipping Address", "status": "error"})
				raise Authexp({"message": errmsg})
			errors = data["data"]["createAccountAddress"]["errors"]
			if len(errors) == 0: #sets the store closest to postal code
				shipp_id =  data["data"]["createAccountAddress"]["newAddress"]["id"]
				b = {
				  "query":"mutation setShipping( $cartId:ID! $addressId:String! $fetchCartFragment:Boolean! = false $includePartialFulfillmentSwitching:Boolean! = false $enableAEBadge:Boolean! = false $includeQueueing:Boolean! = false $includeExpressSla:Boolean! = false $enableACCScheduling:Boolean! = false ){fulfillmentMutations{setShipping(input:{cartId:$cartId addressId:$addressId}){...AccountFragment @skip(if:$fetchCartFragment)...CartFragment @include(if:$fetchCartFragment)}}}fragment AccountFragment on Cart{id fulfillment{homepageBookslotDetails{title subTitle expiryText slotExpiryText expiryTime}}}fragment CartFragment on Cart{id checkoutable customer{id isGuest}cartGiftingDetails{isGiftOrder hasGiftEligibleItem isAddOnServiceAdjustmentNeeded isWalmartProtectionPlanPresent isAppleCarePresent}addressMode migrationLineItems{quantity quantityLabel quantityString accessibilityQuantityLabel offerId usItemId productName thumbnailUrl addOnService priceInfo{linePrice{value displayValue}}selectedVariants{name value}}lineItems{id quantity quantityString quantityLabel hasShippingRestriction isPreOrder isGiftEligible isSubstitutionSelected displayAddOnServices createdDateTime discounts{key displayValue displayLabel value terms subType}isWplusEarlyAccess isEventActive eventType selectedAddOnServices{offerId quantity groupType isGiftEligible error{code upstreamErrorCode errorMsg}}bundleComponents{offerId quantity product{name usItemId imageInfo{thumbnailUrl}}}registryId fulfillmentPreference selectedVariants{name value}priceInfo{priceDisplayCodes{showItemPrice priceDisplayCondition finalCostByWeight}itemPrice{...lineItemPriceInfoFragment}wasPrice{...lineItemPriceInfoFragment}unitPrice{...lineItemPriceInfoFragment}linePrice{...lineItemPriceInfoFragment}}product{id name usItemId sponsoredProduct{spQs clickBeacon spTags}sellerDisplayName fulfillmentBadge variants{availabilityStatus}seller{name sellerId}imageInfo{thumbnailUrl}addOnServices{serviceType serviceTitle serviceSubTitle groups{groupType groupTitle assetUrl shortDescription services{displayName selectedDisplayName offerId usItemId currentPrice{priceString price}serviceMetaData giftEligible}}}itemType offerId sellerId sellerName hasSellerBadge orderLimit orderMinLimit weightUnit weightIncrement salesUnit salesUnitType sellerType isAlcohol fulfillmentType fulfillmentSpeed fulfillmentTitle classType rhPath availabilityStatus brand category{categoryPath}departmentName configuration snapEligible preOrder{isPreOrder}badges @include(if:$enableAEBadge){...BadgesFragment}shippingOption{shipPrice{priceString}}}registryInfo{registryId registryType}wirelessPlan{planId mobileNumber postPaidPlan{...postpaidPlanDetailsFragment}}fulfillmentSourcingDetails{currentSelection requestedSelection fulfillmentBadge}availableQty expiresAt @include(if:$includeQueueing) showExpirationTimer @include(if:$includeQueueing)}fulfillment{intent accessPoint{...accessPointCartFragment}reservation{...reservationFragment}storeId displayStoreSnackBarMessage homepageBookslotDetails{title subTitle expiryText expiryTime slotExpiryText}deliveryAddress{addressLineOne addressLineTwo city state postalCode firstName lastName id phone}fulfillmentItemGroups{...on FCGroup{__typename defaultMode collapsedItemIds startDate endDate checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...priceTotalFields}}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}shippingOptions{__typename itemIds availableShippingOptions{__typename id shippingMethod deliveryDate price{__typename displayValue value}label{prefix suffix}isSelected isDefault slaTier}}hasMadeShippingChanges slaGroups{__typename label deliveryDate sellerGroups{__typename id name isProSeller type catalogSellerId shipOptionGroup{__typename deliveryPrice{__typename displayValue value}itemIds shipMethod}}warningLabel}}...on SCGroup{__typename defaultMode collapsedItemIds checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...priceTotalFields}}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}itemGroups{__typename label itemIds accessPoint{...accessPointCartFragment}}accessPoint{...accessPointCartFragment}reservation{...reservationFragment}}...on DigitalDeliveryGroup{__typename defaultMode collapsedItemIds checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...priceTotalFields}}itemGroups{__typename label itemIds accessPoint{...accessPointCartFragment}}}...on Unscheduled{__typename defaultMode collapsedItemIds checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...priceTotalFields}}itemGroups{__typename label itemIds accessPoint{...accessPointCartFragment}}accessPoint{...accessPointCartFragment}reservation{...reservationFragment}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}isSpecialEvent @include(if:$enableAEBadge)}...on AutoCareCenter{__typename defaultMode collapsedItemIds startDate endDate accBasketType checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...priceTotalFields}}itemGroups{__typename label itemIds accessPoint{...accessPointCartFragment}}accFulfillmentGroups @include(if:$enableACCScheduling){collapsedItemIds itemGroupType reservation{...reservationFragment}suggestedSlotAvailability{...suggestedSlotAvailabilityFragment}itemGroups{__typename label itemIds}}accessPoint{...accessPointCartFragment}reservation{...reservationFragment}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}}}suggestedSlotAvailability{...suggestedSlotAvailabilityFragment}}priceDetails{subTotal{...priceTotalFields}fees{...priceTotalFields}taxTotal{...priceTotalFields}grandTotal{...priceTotalFields}belowMinimumFee{...priceTotalFields}minimumThreshold{value displayValue}ebtSnapMaxEligible{displayValue value}balanceToMinimumThreshold{value displayValue}totalItemQuantity}affirm{isMixedPromotionCart message{description termsUrl imageUrl monthlyPayment termLength isZeroAPR}nonAffirmGroup{...nonAffirmGroupFields}affirmGroups{...on AffirmItemGroup{__typename message{description termsUrl imageUrl monthlyPayment termLength isZeroAPR}flags{type displayLabel}name label itemCount itemIds defaultMode}}}checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}checkoutableWarnings{code itemIds}operationalErrors{offerId itemId requestedQuantity adjustedQuantity code upstreamErrorCode}cartCustomerContext{...cartCustomerContextFragment}}fragment postpaidPlanDetailsFragment on PostPaidPlan{espOrderSummaryId espOrderId espOrderLineId warpOrderId warpSessionId isPostpaidExpired devicePayment{...postpaidPlanPriceFragment}devicePlan{price{...postpaidPlanPriceFragment}frequency duration annualPercentageRate}deviceDataPlan{...deviceDataPlanFragment}}fragment deviceDataPlanFragment on DeviceDataPlan{carrierName planType expiryTime activationFee{...postpaidPlanPriceFragment}planDetails{price{...postpaidPlanPriceFragment}frequency name}agreements{...agreementFragment}}fragment postpaidPlanPriceFragment on PriceDetailRow{key label displayValue value strikeOutDisplayValue strikeOutValue info{title message}}fragment agreementFragment on CarrierAgreement{name type format value docTitle label}fragment priceTotalFields on PriceDetailRow{label displayValue value key strikeOutDisplayValue strikeOutValue}fragment lineItemPriceInfoFragment on Price{displayValue value}fragment accessPointCartFragment on AccessPoint{id assortmentStoreId name nodeAccessType accessType fulfillmentType fulfillmentOption displayName timeZone bagFeeValue isActive address{addressLineOne addressLineTwo city postalCode state phone}}fragment suggestedSlotAvailabilityFragment on SuggestedSlotAvailability{isPickupAvailable isDeliveryAvailable nextPickupSlot{startTime endTime slaInMins}nextDeliverySlot{startTime endTime slaInMins}nextUnscheduledPickupSlot{startTime endTime slaInMins}nextSlot{__typename...on RegularSlot{fulfillmentOption fulfillmentType startTime}...on DynamicExpressSlot{fulfillmentOption fulfillmentType startTime slaInMins sla{value displayValue}}...on UnscheduledSlot{fulfillmentOption fulfillmentType startTime unscheduledHoldInDays}...on InHomeSlot{fulfillmentOption fulfillmentType startTime}}}fragment reservationFragment on Reservation{expiryTime isUnscheduled expired showSlotExpiredError reservedSlot{__typename...on RegularSlot{id price{total{value displayValue}expressFee{value displayValue}baseFee{value displayValue}memberBaseFee{value displayValue}}nodeAccessType accessPointId fulfillmentOption startTime fulfillmentType slotMetadata endTime available supportedTimeZone isAlcoholRestricted}...on DynamicExpressSlot{id price{total{value displayValue}expressFee{value displayValue}baseFee{value displayValue}memberBaseFee{value displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata available sla @include(if:$includeExpressSla){value displayValue}slaInMins maxItemAllowed supportedTimeZone isAlcoholRestricted}...on UnscheduledSlot{price{total{value displayValue}expressFee{value displayValue}baseFee{value displayValue}memberBaseFee{value displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata unscheduledHoldInDays supportedTimeZone}...on InHomeSlot{id price{total{value displayValue}expressFee{value displayValue}baseFee{value displayValue}memberBaseFee{value displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata endTime available supportedTimeZone isAlcoholRestricted}}}fragment nonAffirmGroupFields on NonAffirmGroup{label itemCount itemIds collapsedItemIds}fragment cartCustomerContextFragment on CartCustomerContext{isMembershipOptedIn isEligibleForFreeTrial membershipData{isActiveMember isPaidMember}paymentData{hasCreditCard hasCapOne hasDSCard hasEBT isCapOneLinked showCapOneBanner}}fragment BadgesFragment on UnifiedBadge{flags{__typename...on BaseBadge{id text key query}...on PreviouslyPurchasedBadge{id text key lastBoughtOn numBought criteria{name value}}}labels{__typename...on BaseBadge{id text key}...on PreviouslyPurchasedBadge{id text key lastBoughtOn numBought}}tags{__typename...on BaseBadge{id text key}...on PreviouslyPurchasedBadge{id text key}}}",
				  "variables":{
					 "cartId": self.cart_id,
					 "addressId":shipp_id
					}
				}       
				self.header["x-o-gql-query"] = "mutation setShipping"
				self.header["x-apollo-operation-name"] = "setShipping"
				r = self.session.post("https://www.walmart.com/orchestra/home/graphql", headers=self.header, data=json.dumps(b))
				
				if r.status_code == 200:
					self.status_signal.emit({"msg": "Shipping Method Added", "status": "normal"})
					return 
				else:
					self.status_signal.emit({"msg": "Error Adding Shipping Method", "status": "error"})
					raise Internalexp()
			else:
				print(errors)
					
	def get_PIE(self, card_number):
		headers = {
			"Accept": "*/*",
			"Accept-Encoding": "gzip, deflate, br",
			"Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
			"Connection": "keep-alive",
			"Host": "securedataweb.walmart.com",
			"Referer": "https://www.walmart.com/",
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36",
			
		}
		profile = self.profile
		self.status_signal.emit({"msg": "Getting Checkout Data", "status": "normal"})
		r = self.session.get(
			"https://securedataweb.walmart.com/pie/v1/wmcom_us_vtg_pie/getkey.js?bust=" + str(int(time.time())), headers=headers)
		
		if self.is_captcha(r.text):
			raise captchaExp()
		
		if r.status_code == 200:
			PIE_L = int(r.text.split("PIE.L = ")[1].split(";")[0])
			PIE_E = int(r.text.split("PIE.E = ")[1].split(";")[0])
			PIE_K = str(r.text.split('PIE.K = "')[1].split('";')[0])
			PIE_key_id = str(r.text.split('PIE.key_id = "')[1].split('";')[0])
			PIE_phase = int(r.text.split('PIE.phase = ')[1].split(';')[0])
			card_data = w_e.encrypt(card_number, profile["card_cvv"], PIE_L, PIE_E, PIE_K,
									PIE_key_id, PIE_phase)
			self.status_signal.emit({"msg": "Got Checkout Data", "status": "normal"})
			return card_data, PIE_key_id, PIE_phase
		
		self.status_signal.emit({"msg": "Error Getting Checkout Data", "status": "error"})
		raise Internalexp()

	@safe_execute
	def add_payment(self, card_data, PIE_key_id, PIE_phase):
		self.header["x-o-gql-query"] = "mutation CreateAccountCreditCard"
		self.header["x-apollo-operation-name"] = "CreateAccountCreditCard"
		b = {
		   "query":"mutation CreateAccountCreditCard($input:AccountCreditCardInput!){createAccountCreditCard(input:$input){errors{code message}creditCard{...CreditCardFragment}}}fragment CreditCardFragment on CreditCard{__typename firstName lastName nameOnCard phone addressLineOne addressLineTwo city state postalCode cardType expiryYear expiryMonth lastFour id isDefault isExpired needVerifyCVV isEditable capOneProperties{shouldPromptForLink}linkedCard{availableCredit currentCreditBalance currentMinimumAmountDue minimumPaymentDueDate statementBalance statementDate rewards{rewardsBalance rewardsCurrency cashValue cashDisplayValue canRedeem}links{linkMethod linkHref linkType}}}",
		   "variables":{
			  "input":{
				 "firstName": self.profile["firstName"],
				 "lastName":self.profile["lastName"],
				 "expiryMonth":self.profile["expiryMonth"],
				 "expiryYear":self.profile["expiryYear"],
				 "isDefault":False,
				 "phone":self.profile["phone"],
				 "address":{
					"addressLineOne":self.profile["addressLineOne"],
					"addressLineTwo":self.profile["addressLineTwo"],
					"postalCode":self.profile["postalCode"],
					"city":self.profile["city"],
					"state":self.profile["state"],
					"isApoFpo": None,
					"isLoadingDockAvailable": None,
					"isPoBox": None,
					"businessName": None,
					"addressType": None,
					"sealedAddress": None
				 },
				 "cardType": self.profile["cardType"],
				 "integrityCheck":card_data[2],
				 "keyId":PIE_key_id,
				 "phase":str(PIE_phase),
				 "encryptedPan":card_data[0],
				 "encryptedCVV":card_data[1],
				 "sourceFeature":"ACCOUNT_PAGE",
				 "cartId":None,
				 "checkoutSessionId":None
			  }
		   }
		}
		
		self.status_signal.emit({"msg": "adding Payment", "status": "normal"})
		r = self.session.post("https://www.walmart.com/orchestra/home/graphql", json=b, headers=self.header)
		if self.is_captcha(r.text):
			raise captchaExp()
		if r.status_code == 200:
			try:
				data = json.loads(r.text)
				card_id = data["data"]["createAccountCreditCard"]["creditCard"]["id"]
				self.status_signal.emit({"msg": "added Payment", "status": "normal"})
				return card_id
			except:
				try:
					if len(data["errors"]) != 0:
						self.status_signal.emit({"msg": "error adding credit card, please check your credit card info", "status": "normal"})
						raise Authexp({"message": "credit card is not valid"})
						return 
				except:
					try:
						err_code = data["data"]["createAccountCreditCard"]["errors"][0]["code"]
						if err_code == "ERROR_AVS_REJECTED":
							self.status_signal.emit({"msg": "credit card was rejected by walmart please check card info or use another", "status": "normal"})
							raise Authexp({"message": "credit card was rejected"})
					except:
						pass
		else:
			self.status_signal.emit({"msg": "Error adding Payment", "status": "error"})
			raise Internalexp()
			  
	@safe_execute
	def get_checkout_ids(self):
		self.header["x-o-gql-query"] = "mutation CreateContract"
		self.header["x-apollo-operation-name"] = "CreateContract"
		b1 = {
		   "query":"mutation CreateContract( $createContractInput:CreatePurchaseContractInput! $promosEnable:Boolean! $enableFulfillmentLabels:Boolean! = false $wplusEnabled:Boolean! ){createPurchaseContract(input:$createContractInput){...ContractFragment}}fragment ContractFragment on PurchaseContract{id associateDiscountStatus addressMode tenderPlanId papEbtAllowed allowedPaymentGroupTypes cartCustomerContext{membershipData{isActiveMember status isActiveMember}}cartCustomerContext @include(if:$wplusEnabled){isMembershipOptedIn isEligibleForFreeTrial paymentData{hasCreditCard hasPaymentCardOnFile}membershipData{isPaidMember}}cartCustomerContext @skip(if:$wplusEnabled){paymentData{hasPaymentCardOnFile}membershipData{isPaidMember}}checkoutError{code errorData{__typename...on OutOfStock{offerId}__typename...on UnavailableOffer{offerId}__typename...on ItemExpired{offerId}__typename...on ItemQuantityAdjusted{offerId requestedQuantity adjustedQuantity}__typename...on AppointmentExpired{offerId}}operationalErrorCode message}checkoutableWarnings{code itemIds}allocationStatus payments{id paymentType cardType lastFour isDefault cvvRequired preferenceId paymentPreferenceId paymentHandle expiryMonth expiryYear firstName lastName email amountPaid cardImage cardImageAlt isLinkedCard capOneReward{credentialId redemptionUrl redemptionRate redemptionMethod rewardPointsBalance rewardPointsSelected rewardAmountSelected}remainingBalance{displayValue value}}order{id status orderVersion mobileNumber}terms{alcoholAccepted bagFeeAccepted smsOptInAccepted marketingEmailPrefOptIn}donationDetails{charityEIN charityName amount{displayValue value}acceptDonation}lineItems{...LineItemFields}tippingDetails{suggestedAmounts{value displayValue}maxAmount{value displayValue}selectedTippingAmount{value displayValue}}customer{id firstName lastName isGuest email phone}fulfillment{deliveryDetails{deliveryInstructions deliveryOption}pickupChoices{isSelected fulfillmentType cartFulfillmentType accessType accessMode accessPointId}deliveryAddress{...AddressFields}alternatePickupPerson{...PickupPersonFields}primaryPickupPerson{...PickupPersonFields}fulfillmentItemGroups{...FulfillmentItemGroupsFields}}priceDetails{subTotal{...PriceDetailRowFields}totalItemQuantity fees{...PriceDetailRowFields}taxTotal{...PriceDetailRowFields}grandTotal{...PriceDetailRowFields}belowMinimumFee{...PriceDetailRowFields}authorizationAmount{...PriceDetailRowFields}weightDebitTotal{...PriceDetailRowFields}discounts{...PriceDetailRowFields}otcDeliveryBenefit{...PriceDetailRowFields}ebtSnapMaxEligible{...PriceDetailRowFields}ebtCashMaxEligible{...PriceDetailRowFields}hasAmountUnallocated affirm{__typename message{...AffirmMessageFields}}}checkoutGiftingDetails{isCheckoutGiftingOptin isWalmartProtectionPlanPresent isAppleCarePresent isRestrictedPaymentPresent giftMessageDetails{giftingMessage recipientEmail recipientName senderName}}promotions @include(if:$promosEnable){displayValue promoId terms}serverTime showPromotions @include(if:$promosEnable) errors{code message lineItems{...LineItemFields}}}fragment LineItemFields on LineItem{id quantity quantityString quantityLabel accessibilityQuantityLabel isPreOrder isWplusEarlyAccess isEventActive eventType fulfillmentSourcingDetails{currentSelection requestedSelection}packageQuantity priceInfo{priceDisplayCodes{showItemPrice priceDisplayCondition finalCostByWeight}itemPrice{displayValue value}linePrice{displayValue value}preDiscountedLinePrice{displayValue value}wasPrice{displayValue value}unitPrice{displayValue value}}isSubstitutionSelected isGiftEligible expiresAt showExpirationTimer selectedVariants{name value}product{...ProductFields}discounts{key label value @include(if:$promosEnable) terms subType displayValue @include(if:$promosEnable) displayLabel}wirelessPlan{planId mobileNumber __typename postPaidPlan{...postpaidPlanDetailsFragment}}selectedAddOnServices{offerId quantity groupType}registryInfo{registryId registryType}}fragment postpaidPlanDetailsFragment on PostPaidPlan{__typename espOrderSummaryId espOrderId espOrderLineId warpOrderId warpSessionId devicePayment{...postpaidPlanPriceFragment}devicePlan{__typename price{...postpaidPlanPriceFragment}frequency duration annualPercentageRate}deviceDataPlan{...deviceDataPlanFragment}}fragment deviceDataPlanFragment on DeviceDataPlan{__typename carrierName planType expiryTime activationFee{...postpaidPlanPriceFragment}planDetails{__typename price{...postpaidPlanPriceFragment}frequency name}agreements{...agreementFragment}}fragment postpaidPlanPriceFragment on PriceDetailRow{__typename key label displayValue value strikeOutDisplayValue strikeOutValue info{__typename title message}}fragment agreementFragment on CarrierAgreement{__typename name type format value docTitle label}fragment preOrderFragment on PreOrder{streetDate streetDateDisplayable streetDateType isPreOrder preOrderMessage preOrderStreetDateMessage}fragment AddressFields on Address{id addressLineOne addressLineTwo city state postalCode firstName lastName phone}fragment PickupPersonFields on PickupPerson{id firstName lastName email}fragment PriceDetailRowFields on PriceDetailRow{__typename key label displayValue value strikeOutValue strikeOutDisplayValue info{__typename title message}}fragment AccessPointFields on AccessPoint{id name assortmentStoreId displayName timeZone address{id addressLineOne addressLineTwo city state postalCode firstName lastName phone}isTest allowBagFee bagFeeValue isExpressEligible fulfillmentOption instructions nodeAccessType}fragment ReservationFields on Reservation{id expiryTime isUnscheduled expired showSlotExpiredError reservedSlot{__typename...on RegularSlot{id price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata slotExpiryTime endTime available supportedTimeZone}...on DynamicExpressSlot{id price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId fulfillmentOption startTime endTime fulfillmentType slotMetadata slotExpiryTime available slaInMins sla{value displayValue}maxItemAllowed supportedTimeZone}...on UnscheduledSlot{price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata unscheduledHoldInDays supportedTimeZone}...on InHomeSlot{id price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata slotExpiryTime endTime available supportedTimeZone}}}fragment AffirmMessageFields on AffirmMessage{__typename description termsUrl imageUrl monthlyPayment termLength isZeroAPR}fragment FulfillmentItemGroupsFields on FulfillmentItemGroup{...on SCGroup{__typename defaultMode collapsedItemIds itemGroups{__typename label itemIds}accessPoint{...AccessPointFields}reservation{...ReservationFields}}...on DigitalDeliveryGroup{__typename defaultMode collapsedItemIds itemGroups{__typename label itemIds}}...on Unscheduled{__typename defaultMode collapsedItemIds isSpecialEvent startDate endDate itemGroups{__typename label itemIds}accessPoint{...AccessPointFields}reservation{...ReservationFields}}...on FCGroup{__typename defaultMode collapsedItemIds startDate endDate isUnscheduledDeliveryEligible shippingOptions{__typename itemIds availableShippingOptions{__typename id shippingMethod deliveryDate price{__typename displayValue value}label{prefix suffix}isSelected isDefault}}hasMadeShippingChanges slaGroups{__typename label deliveryDate warningLabel sellerGroups{__typename id name isProSeller type shipOptionGroup{__typename deliveryPrice{__typename displayValue value}itemIds shipMethod}}}}...on AutoCareCenter{__typename defaultMode startDate endDate accBasketType collapsedItemIds itemGroups{__typename label itemIds}accessPoint{...AccessPointFields}reservation{...ReservationFields}}}fragment ProductFields on Product{id name usItemId itemType imageInfo{thumbnailUrl}category{categoryPath}fulfillmentLabel @include(if:$enableFulfillmentLabels){checkStoreAvailability wPlusFulfillmentText message shippingText fulfillmentText locationText fulfillmentMethod addressEligibility fulfillmentType postalCode}offerId orderLimit orderMinLimit weightIncrement weightUnit averageWeight salesUnitType availabilityStatus isSubstitutionEligible isAlcohol configuration hasSellerBadge sellerId sellerName sellerType annualEvent preOrder{...preOrderFragment}badges{flags{__typename id key text}}addOnServices{serviceType groups{groupType services{selectedDisplayName offerId currentPrice{priceString}}}}}",
		   "variables":{
			  "createContractInput":{
				 "cartId": self.cart_id
			  },
			  "enableWalmartPlusFreeDiscountedExpress": False,
	          "isACCEnabled": True,
			  "promosEnable":True,
			  "wplusEnabled":True
		   }
		}
		r = self.session.post("https://www.walmart.com/orchestra/cartxo/graphql", data=json.dumps(b1), headers=self.header)
		data = json.loads(r.text)
		if self.is_captcha(r.text):
			raise captchaExp()
		try:
			contract_id = data["data"]["createPurchaseContract"]["id"]
			ipurchase_id = data["data"]["createPurchaseContract"]["lineItems"][0]["id"]
		except:
			print(data)
			err = data["errors"][0]["message"]
			if "Checkoutable is false" in err:
				raise Internalexp("item is not checkoutable either cart is empty or shipping not set")

		header = {'content-length': '3547', 'sec-ch-ua': '" Not;A Brand";v="99", "Google Chrome";v="97", "Chromium";v="97"', 'x-o-platform': 'rweb', 'dnt': '1', 'x-o-correlation-id': ''.join(random.choice(string.digits + string.ascii_uppercase + string.ascii_lowercase) for _ in range(36)),'device_profile_ref_id': ''.join(random.choice(string.digits + string.ascii_uppercase + string.ascii_lowercase) for _ in range(36)), 'x-latency-trace': '1', 'wm_mp': 'true', 'x-o-market': 'us', 'x-o-platform-version': 'main-420-626f2c', 'x-o-gql-query': 'query getTenderPlan', 'x-apollo-operation-name': 'getTenderPlan', 'sec-ch-ua-platform': '"Windows"', 'sec-ch-ua-mobile': '?0', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36', 'x-o-segment': 'oaoh', 'content-type': 'application/json', 'accept': 'application/json', 'x-enable-server-timing': '1', 'x-o-ccm': 'server', 'x-o-tp-phase': 'tp5', 'wm_qos.correlation_id': 'ZGjjT-ik2nwM-t4eyFdulC4y_TDwt1wlXvLz', 'origin': 'https', 'sec-fetch-site': 'same-origin', 'sec-fetch-mode': 'cors', 'sec-fetch-dest': 'empty', 'referer': 'https', 'accept-encoding': 'gzip, deflate, br', 'accept-language': 'en-US,en;q=0.9,fr;q=0.8,ar;q=0.7'}
		self.referer = "https://www.walmart.com/checkout/review-order?cartId={}&wv=main".format(self.cart_id)
		header["referer"] = self.referer
		b2 = {
			"query": "query getTenderPlan($tenderPlanInput:TenderPlanInput!){tenderPlan(input:$tenderPlanInput){__typename tenderPlan{...TenderPlanFields}}}fragment TenderPlanFields on TenderPlan{__typename id contractId grandTotal{...PriceDetailRowFields}authorizationAmount{...PriceDetailRowFields}allocationStatus paymentGroups{...PaymentGroupFields}otcDeliveryBenefit{...PriceDetailRowFields}otherAllowedPayments{type status}addPaymentType hasAmountUnallocated weightDebitTotal{...PriceDetailRowFields}}fragment PriceDetailRowFields on PriceDetailRow{__typename key label displayValue value info{__typename title message}}fragment PaymentGroupFields on TenderPlanPaymentGroup{__typename type subTotal{__typename key label displayValue value info{__typename title message}}selectedCount allocations{...CreditCardAllocationFragment...GiftCardAllocationFragment...EbtCardAllocationFragment...DsCardAllocationFragment...PayPalAllocationFragment...AffirmAllocationFragment}statusMessage}fragment CreditCardAllocationFragment on CreditCardAllocation{__typename card{...CreditCardFragment}canEditOrDelete canDeselect isEligible isSelected allocationAmount{__typename displayValue value}capOneReward{...CapOneFields}statusMessage{__typename messageStatus messageType}paymentType}fragment CapOneFields on CapOneReward{credentialId redemptionRate redemptionUrl redemptionMethod rewardPointsBalance rewardPointsSelected rewardAmountSelected}fragment CreditCardFragment on CreditCard{__typename id isDefault cardAccountLinked needVerifyCVV cardType expiryMonth expiryYear isExpired firstName lastName lastFour nameOnCard isEditable phone}fragment GiftCardAllocationFragment on GiftCardAllocation{__typename card{...GiftCardFields}canEditOrDelete canDeselect isEligible isSelected allocationAmount{__typename displayValue value}statusMessage{__typename messageStatus messageType}paymentType remainingBalance{__typename displayValue value}}fragment GiftCardFields on GiftCard{__typename id balance{cardBalance}lastFour displayLabel}fragment EbtCardAllocationFragment on EbtCardAllocation{__typename card{__typename id lastFour firstName lastName}canEditOrDelete canDeselect isEligible isSelected allocationAmount{__typename displayValue value}statusMessage{__typename messageStatus messageType}paymentType ebtMaxEligibleAmount{__typename displayValue value}cardBalance{__typename displayValue value}}fragment DsCardAllocationFragment on DsCardAllocation{__typename card{...DsCardFields}canEditOrDelete canDeselect isEligible isSelected allocationAmount{__typename displayValue value}statusMessage{__typename messageStatus messageType}paymentType canApplyAmount{__typename displayValue value}remainingBalance{__typename displayValue value}paymentPromotions{__typename programName processorPromotionCode canApplyAmount{__typename displayValue value}allocationAmount{__typename displayValue value}remainingBalance{__typename displayValue value}balance{__typename displayValue value}termsLink isInvalid}otcShippingBenefit termsLink}fragment DsCardFields on DsCard{__typename id displayLabel lastFour fundingProgram balance{cardBalance}dsCardType cardName}fragment PayPalAllocationFragment on PayPalAllocation{__typename allocationAmount{__typename displayValue value}paymentHandle paymentType email}fragment AffirmAllocationFragment on AffirmAllocation{__typename allocationAmount{__typename displayValue value}paymentHandle paymentType cardType firstName lastName}",
			"variables": {
				"tenderPlanInput": {
					"contractId": contract_id,
					"isAmendFlow": False
				}
			}
		}
		r = self.session.post("https://www.walmart.com/orchestra/cartxo/graphql", data=json.dumps(b2), headers=header)
		data = json.loads(r.text)
		try:
			tenderplan_id = data["data"]["tenderPlan"]["tenderPlan"]["id"]
			return contract_id, tenderplan_id, ipurchase_id
		except:
			print("error getting tenderplan_id text:")
			if self.is_captcha(r.text):
				raise captchaExp()

	@safe_execute
	def submit_payment(self, contract_id, tenderplan_id, card_id):
		self.status_signal.emit({"msg": "submitting payment", "status": "normal"})
		header = {'content-length': '3778', 'pragma': 'no-cache', 'cache-control': 'no-cache', 'x-o-platform': 'rweb', 'dnt': '1', 'x-o-correlation-id': ''.join(random.choice(string.digits + string.ascii_uppercase + string.ascii_lowercase) for _ in range(36)), 'device_profile_ref_id': ''.join(random.choice(string.digits + string.ascii_uppercase + string.ascii_lowercase) for _ in range(36)), 'x-latency-trace': '1', 'wm_mp': 'true', 'x-o-market': 'us', 'x-o-platform-version': 'main-420-626f2c', 'x-o-gql-query': 'mutation updateTenderPlan', 'x-apollo-operation-name': 'updateTenderPlan', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36', 'x-o-segment': 'oaoh', 'content-type': 'application/json', 'accept': 'application/json', 'x-enable-server-timing': '1', 'x-o-ccm': 'server', 'x-o-tp-phase': 'tp5', 'wm_qos.correlation_id': 'UgUJQm7Ggx7vWQfo216kEoH4zKSOJZxPKvmC', 'origin': 'https', 'sec-fetch-site': 'same-origin', 'sec-fetch-mode': 'cors', 'sec-fetch-dest': 'empty', 'referer': 'https', 'accept-encoding': 'gzip, deflate, br', 'accept-language': 'en-US,en;q=0.9,fr;q=0.8,ar;q=0.7'}
		# header["referer"] = self.referer
		header["origin"] = "https://www.walmart.com"
		b = {
			"query": "mutation updateTenderPlan($input:UpdateTenderPlanInput!){updateTenderPlan(input:$input){__typename tenderPlan{...TenderPlanFields}}}fragment TenderPlanFields on TenderPlan{__typename id contractId grandTotal{...PriceDetailRowFields}authorizationAmount{...PriceDetailRowFields}allocationStatus paymentGroups{...PaymentGroupFields}otcDeliveryBenefit{...PriceDetailRowFields}otherAllowedPayments{type status}addPaymentType hasAmountUnallocated weightDebitTotal{...PriceDetailRowFields}}fragment PriceDetailRowFields on PriceDetailRow{__typename key label displayValue value info{__typename title message}}fragment PaymentGroupFields on TenderPlanPaymentGroup{__typename type subTotal{__typename key label displayValue value info{__typename title message}}selectedCount allocations{...CreditCardAllocationFragment...GiftCardAllocationFragment...EbtCardAllocationFragment...DsCardAllocationFragment...PayPalAllocationFragment...AffirmAllocationFragment}statusMessage}fragment CreditCardAllocationFragment on CreditCardAllocation{__typename card{...CreditCardFragment}canEditOrDelete canDeselect isEligible isSelected allocationAmount{__typename displayValue value}capOneReward{...CapOneFields}statusMessage{__typename messageStatus messageType}paymentType}fragment CapOneFields on CapOneReward{credentialId redemptionRate redemptionUrl redemptionMethod rewardPointsBalance rewardPointsSelected rewardAmountSelected}fragment CreditCardFragment on CreditCard{__typename id isDefault cardAccountLinked needVerifyCVV cardType expiryMonth expiryYear isExpired firstName lastName lastFour nameOnCard isEditable phone}fragment GiftCardAllocationFragment on GiftCardAllocation{__typename card{...GiftCardFields}canEditOrDelete canDeselect isEligible isSelected allocationAmount{__typename displayValue value}statusMessage{__typename messageStatus messageType}paymentType remainingBalance{__typename displayValue value}}fragment GiftCardFields on GiftCard{__typename id balance{cardBalance}lastFour displayLabel}fragment EbtCardAllocationFragment on EbtCardAllocation{__typename card{__typename id lastFour firstName lastName}canEditOrDelete canDeselect isEligible isSelected allocationAmount{__typename displayValue value}statusMessage{__typename messageStatus messageType}paymentType ebtMaxEligibleAmount{__typename displayValue value}cardBalance{__typename displayValue value}}fragment DsCardAllocationFragment on DsCardAllocation{__typename card{...DsCardFields}canEditOrDelete canDeselect isEligible isSelected allocationAmount{__typename displayValue value}statusMessage{__typename messageStatus messageType}paymentType canApplyAmount{__typename displayValue value}remainingBalance{__typename displayValue value}paymentPromotions{__typename programName processorPromotionCode canApplyAmount{__typename displayValue value}allocationAmount{__typename displayValue value}remainingBalance{__typename displayValue value}balance{__typename displayValue value}termsLink isInvalid}otcShippingBenefit termsLink}fragment DsCardFields on DsCard{__typename id displayLabel lastFour fundingProgram balance{cardBalance}dsCardType cardName}fragment PayPalAllocationFragment on PayPalAllocation{__typename allocationAmount{__typename displayValue value}paymentHandle paymentType email}fragment AffirmAllocationFragment on AffirmAllocation{__typename allocationAmount{__typename displayValue value}paymentHandle paymentType cardType firstName lastName}",
			"variables": {
				"input": {
					"accountRefresh": None,
					"contractId": contract_id,
					"isAmendFlow": False,
					"payments": [
						{
							"amount": None,
							"capOneReward": None,
							"cardType": None,
							"paymentHandle": None,
							"paymentType": "CREDITCARD",
							"preferenceId": card_id
						}
					],
					"tenderPlanId": tenderplan_id
				}
			}
		}
		r = self.session.post("https://www.walmart.com/orchestra/cartxo/graphql", data=json.dumps(b), headers=header)
		data = json.loads(r.text)
		tenderplan_id = data["data"]["updateTenderPlan"]["tenderPlan"]["id"]
		if self.is_captcha(r.text):
			raise captchaExp()
		header = {'pragma': 'no-cache', 'cache-control': 'no-cache', 'x-o-platform': 'rweb', 'dnt': '1', 'x-o-correlation-id': ''.join(random.choice(string.digits + string.ascii_uppercase + string.ascii_lowercase) for _ in range(36)), 'device_profile_ref_id': ''.join(random.choice(string.digits + string.ascii_uppercase + string.ascii_lowercase) for _ in range(36)), 'x-latency-trace': '1', 'wm_mp': 'true', 'x-o-market': 'us', 'x-o-platform-version': 'main-420-626f2c', 'x-o-gql-query': 'mutation updateTenderPlan', 'x-apollo-operation-name': 'updateTenderPlan', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36', 'x-o-segment': 'oaoh', 'content-type': 'application/json', 'accept': 'application/json', 'x-enable-server-timing': '1', 'x-o-ccm': 'server', 'x-o-tp-phase': 'tp5', 'wm_qos.correlation_id': 'UgUJQm7Ggx7vWQfo216kEoH4zKSOJZxPKvmC', 'origin': 'https', 'sec-fetch-site': 'same-origin', 'sec-fetch-mode': 'cors', 'sec-fetch-dest': 'empty', 'referer': 'https', 'accept-encoding': 'gzip, deflate, br', 'accept-language': 'en-US,en;q=0.9,fr;q=0.8,ar;q=0.7'}
		header["origin"] = "https://www.walmart.com"
		header["x-o-gql-query"] = 'mutation saveTenderPlanToPC'
		header["X-APOLLO-OPERATION-NAME"] = "saveTenderPlanToPC"
		b = {
		   "query":"mutation saveTenderPlanToPC( $input:SaveTenderPlanToPCInput! $promosEnable:Boolean! $enableFulfillmentLabels:Boolean! = false $wplusEnabled:Boolean! $isACCEnabled:Boolean! $enableWalmartPlusFreeDiscountedExpress:Boolean! $enableGroupMetaData:Boolean! = false ){saveTenderPlanToPC(input:$input){...ContractFragment}}fragment ContractFragment on PurchaseContract{id associateDiscountStatus addressMode tenderPlanId papEbtAllowed allowedPaymentGroupTypes cartCustomerContext{membershipData{isActiveMember status isActiveMember}}cartCustomerContext @include(if:$wplusEnabled){isMembershipOptedIn isEligibleForFreeTrial paymentData{hasCreditCard hasPaymentCardOnFile}membershipData{isPaidMember}}cartCustomerContext @skip(if:$wplusEnabled){paymentData{hasPaymentCardOnFile}membershipData{isPaidMember}}checkoutableWarnings{code itemIds}payments{id paymentType cardType lastFour isDefault cvvRequired preferenceId paymentPreferenceId paymentHandle expiryMonth expiryYear firstName lastName email amountPaid cardImage cardImageAlt isLinkedCard capOneReward{credentialId redemptionUrl redemptionRate redemptionMethod rewardPointsBalance rewardPointsSelected rewardAmountSelected}remainingBalance{displayValue value}installmentOptions{term interval minAmount monthlyPayment selected paymentName}twoFactorAuthenticationUrl}order{id status orderVersion mobileNumber estimatedRewards{displayValue}}terms{alcoholAccepted bagFeeAccepted smsOptInAccepted marketingEmailPrefOptIn}donationDetails{charityEIN charityName amount{displayValue value}acceptDonation}lineItems{...LineItemFields}tippingDetails{suggestedAmounts{value displayValue}maxAmount{value displayValue}selectedTippingAmount{value displayValue}}customer{id firstName lastName isGuest email phone}fulfillment{deliveryDetails{deliveryInstructions deliveryOption}pickupChoices{isSelected fulfillmentType cartFulfillmentType accessType accessMode accessPointId}deliveryAddress{...AddressFields}isDeliveryAddressEditable alternatePickupPerson{...PickupPersonFields}primaryPickupPerson{...PickupPersonFields}fulfillmentItemGroups{...FulfillmentItemGroupsFields}storeId}priceDetails{subTotal{...PriceDetailRowFields}totalItemQuantity fees{...PriceDetailRowFields}taxTotal{...PriceDetailRowFields}grandTotal{...PriceDetailRowFields}belowMinimumFee{...PriceDetailRowFields}authorizationAmount{...PriceDetailRowFields}weightDebitTotal{...PriceDetailRowFields}discounts{...PriceDetailRowFields}otcDeliveryBenefit{...PriceDetailRowFields}ebtSnapMaxEligible{...PriceDetailRowFields}ebtCashMaxEligible{...PriceDetailRowFields}originalSubTotal{...PriceDetailRowFields}savedPriceSubTotal{...PriceDetailRowFields}hasGrandTotalChanged hasAmountUnallocated hadMinThresholdFeeDuringPCCreation affirm{__typename message{...AffirmMessageFields}}rewardsEligibility{...RewardsEligibilityFields}}checkoutGiftingDetails{isCheckoutGiftingOptin isWalmartProtectionPlanPresent isAppleCarePresent isRestrictedPaymentPresent giftMessageDetails{giftingMessage recipientEmail recipientName senderName}}promotions @include(if:$promosEnable){displayValue promoId terms}serverTime showPromotions @include(if:$promosEnable)...ContractErrorsFields substitutionSummary{...SubstitutionSummaryFragment}}fragment LineItemFields on LineItem{id quantity quantityString quantityLabel accessibilityQuantityLabel isWplusEarlyAccess isEventActive needsPrescription eventType fulfillmentSourcingDetails{currentSelection requestedSelection}packageQuantity personalizedItemDetails{personalizedConfigID personalizedConfigAttributes{name value}}priceInfo{priceDisplayCodes{showItemPrice priceDisplayCondition finalCostByWeight}itemPrice{displayValue value}linePrice{displayValue value}preDiscountedLinePrice{displayValue value}wasPrice{displayValue value}unitPrice{displayValue value}savedPrice{displayValue value}}isSubstitutionSelected isGiftEligible expiresAt showExpirationTimer selectedVariants{name value}product{...ProductFields}discounts{key label value @include(if:$promosEnable) terms subType displayValue @include(if:$promosEnable) displayLabel}wirelessPlan{planId mobileNumber __typename postPaidPlan{...postpaidPlanDetailsFragment}}selectedAddOnServices{offerId quantity groupType}registryInfo{registryId registryType}}fragment postpaidPlanDetailsFragment on PostPaidPlan{__typename espOrderSummaryId espOrderId espOrderLineId warpOrderId warpSessionId devicePayment{...postpaidPlanPriceFragment}devicePlan{__typename price{...postpaidPlanPriceFragment}frequency duration annualPercentageRate}deviceDataPlan{...deviceDataPlanFragment}}fragment deviceDataPlanFragment on DeviceDataPlan{__typename carrierName planType expiryTime activationFee{...postpaidPlanPriceFragment}planDetails{__typename price{...postpaidPlanPriceFragment}frequency name}agreements{...agreementFragment}}fragment postpaidPlanPriceFragment on PriceDetailRow{__typename key label displayValue value strikeOutDisplayValue strikeOutValue info{__typename title message}}fragment agreementFragment on CarrierAgreement{__typename name type format value docTitle label}fragment preOrderFragment on PreOrder{streetDate isPreOrder}fragment AddressFields on Address{id addressLineOne addressLineTwo city state postalCode firstName lastName phone}fragment PickupPersonFields on PickupPerson{id firstName lastName email}fragment PriceDetailRowFields on PriceDetailRow{__typename key label displayValue value strikeOutValue strikeOutDisplayValue additionalInfo info{__typename title message}program @include(if:$enableWalmartPlusFreeDiscountedExpress)}fragment AccessPointFields on AccessPoint{id name assortmentStoreId displayName timeZone address{id addressLineOne addressLineTwo city state postalCode firstName lastName phone}isTest allowBagFee bagFeeValue isExpressEligible cartFulfillmentOption instructions nodeAccessType}fragment ReservationFields on Reservation{id expiryTime isUnscheduled expired showSlotExpiredError reservedSlot{__typename...on RegularSlot{id price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId cartFulfillmentOption startTime fulfillmentType nodeAccessType slotMetadata slotExpiryTime endTime available supportedTimeZone isPopular}...on DynamicExpressSlot{id price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId cartFulfillmentOption startTime endTime fulfillmentType nodeAccessType slotMetadata slotExpiryTime available slaInMins sla{value displayValue}maxItemAllowed supportedTimeZone}...on UnscheduledSlot{price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId cartFulfillmentOption startTime fulfillmentType nodeAccessType slotMetadata unscheduledHoldInDays supportedTimeZone}...on InHomeSlot{id price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId cartFulfillmentOption startTime fulfillmentType nodeAccessType slotMetadata slotExpiryTime endTime available supportedTimeZone}}}fragment AffirmMessageFields on AffirmMessage{__typename description termsUrl imageUrl monthlyPayment termLength isZeroAPR}fragment FulfillmentItemGroupsFields on FulfillmentItemGroup{...on SCGroup{__typename defaultMode collapsedItemIds itemGroups{__typename label itemIds}accessPoint{...AccessPointFields}reservation{...ReservationFields}pickupLocationCount}...on DigitalDeliveryGroup{__typename defaultMode collapsedItemIds itemGroups{__typename label itemIds}}...on Unscheduled{__typename defaultMode collapsedItemIds isSpecialEvent startDate endDate itemGroups{__typename label itemIds}accessPoint{...AccessPointFields}reservation{...ReservationFields}}...on MPGroup{__typename defaultMode collapsedItemIds startDate endDate itemGroups{__typename label itemIds}accessPoint{...AccessPointFields}reservation{...ReservationFields}}...on FCGroup{__typename defaultMode collapsedItemIds startDate endDate isUnscheduledDeliveryEligible shippingOptions{__typename itemIds availableShippingOptions{__typename id shippingMethod deliveryDate price{__typename displayValue value}label{prefix suffix}isSelected isDefault slaTier}}hasMadeShippingChanges slaGroups{__typename label deliveryDate warningLabel sellerGroups{__typename id name isProSeller type shipOptionGroup{__typename deliveryPrice{__typename displayValue value}itemIds shipMethod}}}}...on AutoCareCenter{__typename defaultMode startDate endDate accBasketType collapsedItemIds itemGroups{__typename label itemIds}accessPoint{...AccessPointFields}reservation{...ReservationFields}accFulfillmentGroups @include(if:$isACCEnabled){...ACCFulfillmentItemGroupFields}}}fragment ACCFulfillmentItemGroupFields on ACCFulfillmentGroup{collapsedItemIds itemGroupType reservation{...ReservationFields}itemGroups{__typename label itemIds}}fragment ProductFields on Product{id name usItemId itemType groupMetaData @include(if:$enableGroupMetaData){groupComponents{offerId quantity}}imageInfo{thumbnailUrl}category{categoryPath categoryPathId}fulfillmentLabel @include(if:$enableFulfillmentLabels){checkStoreAvailability wPlusFulfillmentText message shippingText fulfillmentText locationText fulfillmentMethod addressEligibility fulfillmentType postalCode}offerId orderLimit orderMinLimit weightIncrement weightUnit averageWeight salesUnitType availabilityStatus isSubstitutionEligible isAlcohol configuration hasSellerBadge sellerId sellerName sellerType annualEvent personalizable preOrder{...preOrderFragment}badges{flags{__typename id key text}}addOnServices{serviceType groups{groupType services{selectedDisplayName offerId currentPrice{priceString}}}}type}fragment ContractErrorsFields on PurchaseContract{allocationStatus checkoutError{...CheckoutErrorField}}fragment CheckoutErrorField on CheckoutOperationalError{__typename code message errorData{...on OutOfStock{__typename offerId}...on UnavailableOffer{__typename offerId}...on ItemQuantityAdjusted{__typename offerId requestedQuantity adjustedQuantity}...on ItemExpired{__typename offerId}...on AppointmentExpired{__typename offerId}}operationalErrorCode errorLineItems{...CheckoutErrorLineItemsField}}fragment CheckoutErrorLineItemsField on CheckoutOperationalErrorLineItem{__typename offerId usItemId product{...ProductFields}lineItem{...LineItemFields}}fragment RewardsEligibilityFields on RewardsEligibilityInfo{paymentType cardType preferenceId balance{displayValue value}}fragment SubstitutionSummaryFragment on SubstitutionSummary{hasSubstitutionEligibleItems hasItemsWithSubstitutionPreference}",
		   "variables":{
		      "input":{
		         "contractId":contract_id,
		         "tenderPlanId":tenderplan_id,
		      },
		      "promosEnable":True,
		      "wplusEnabled":True,
		      "isACCEnabled":True,
		      "enableWalmartPlusFreeDiscountedExpress":False
		   }
		}
		r = self.session.post("https://www.walmart.com/orchestra/cartxo/graphql", data=json.dumps(b), headers=header)

		data = json.loads(r.text)
		try:
			if len(data["errors"]) != 0:
				self.status_signal.emit({"msg": "error submitting payment", "status": "error"})
		except Exception as ex:
			self.status_signal.emit({"msg": "payment submitted", "status": "normal"})
		else:
			raise Internalexp()
	
	@safe_execute
	def submit_order(self, contract_id, ipurchase_id, card_id):
		
		header = {'accept': 'application/json', 'accept-encoding': 'gzip, deflate, br', 'accept-language': 'en-US,en;q=0.9,fr;q=0.8,ar;q=0.7', 'cache-control': 'no-cache', 'content-type': 'application/json', 'device_profile_ref_id': 'M_g_70A6OUKwXJMQ1vyu5H8BynxwRo49NJAH', 'dnt': '1', 'origin': 'https', 'pragma': 'no-cache', 'referer': 'https', 'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="98", "Google Chrome";v="98"', 'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"', 'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-origin', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82 Safari/537.36', 'wm_mp': 'true', 'wm_qos.correlation_id': 'xRSppwo38fZtb3HgK9jknAqd-ocRb4zCGE1h', 'x-apollo-operation-name': 'PlaceOrder', 'x-enable-server-timing': '1', 'x-latency-trace': '1', 'x-o-ccm': 'server', 'x-o-correlation-id': 'xRSppwo38fZtb3HgK9jknAqd-ocRb4zCGE1h', 'x-o-gql-query': 'mutation PlaceOrder', 'x-o-market': 'us', 'x-o-platform': 'rweb', 'x-o-platform-version': 'main-496-debfb0', 'x-o-segment': 'oaoh', 'x-o-tp-phase': 'tp5'}
		header["referer"] += self.cart_id 
		card_data, PIE_key_id, PIE_phase = self.encrypt_cvv()
		self.cvv_verify = {
		    "preferenceId": card_id,
		    "paymentType": "CREDITCARD",
		    "encryptedPan": card_data[0],
		    "encryptedCvv": card_data[1],
		    "integrityCheck": card_data[2],
		    "keyId": PIE_key_id,
		    "phase": str(PIE_phase)
		}
		b = {
		    "query": "mutation PlaceOrder( $placeOrderInput:PlaceOrderInput! $promosEnable:Boolean! $enableFulfillmentLabels:Boolean! = false $wplusEnabled:Boolean! $isACCEnabled:Boolean! $onlyFetchCheckoutErrors:Boolean = false $enableWalmartPlusFreeDiscountedExpress:Boolean! ){placeOrder(input:$placeOrderInput){...ContractFragment @skip(if:$onlyFetchCheckoutErrors)...ContractErrorsFields @include(if:$onlyFetchCheckoutErrors)}}fragment ContractFragment on PurchaseContract{id associateDiscountStatus addressMode tenderPlanId papEbtAllowed allowedPaymentGroupTypes cartCustomerContext{membershipData{isActiveMember status isActiveMember}}cartCustomerContext @include(if:$wplusEnabled){isMembershipOptedIn isEligibleForFreeTrial paymentData{hasCreditCard hasPaymentCardOnFile}membershipData{isPaidMember}}cartCustomerContext @skip(if:$wplusEnabled){paymentData{hasPaymentCardOnFile}membershipData{isPaidMember}}checkoutableWarnings{code itemIds}payments{id paymentType cardType lastFour isDefault cvvRequired preferenceId paymentPreferenceId paymentHandle expiryMonth expiryYear firstName lastName email amountPaid cardImage cardImageAlt isLinkedCard capOneReward{credentialId redemptionUrl redemptionRate redemptionMethod rewardPointsBalance rewardPointsSelected rewardAmountSelected}remainingBalance{displayValue value}installmentOptions{term interval minAmount monthlyPayment selected paymentName}twoFactorAuthenticationUrl}order{id status orderVersion mobileNumber estimatedRewards{displayValue}}terms{alcoholAccepted bagFeeAccepted smsOptInAccepted marketingEmailPrefOptIn}donationDetails{charityEIN charityName amount{displayValue value}acceptDonation}lineItems{...LineItemFields}tippingDetails{suggestedAmounts{value displayValue}maxAmount{value displayValue}selectedTippingAmount{value displayValue}}customer{id firstName lastName isGuest email phone}fulfillment{deliveryDetails{deliveryInstructions deliveryOption}pickupChoices{isSelected fulfillmentType cartFulfillmentType accessType accessMode accessPointId}deliveryAddress{...AddressFields}isDeliveryAddressEditable alternatePickupPerson{...PickupPersonFields}primaryPickupPerson{...PickupPersonFields}fulfillmentItemGroups{...FulfillmentItemGroupsFields}storeId}priceDetails{subTotal{...PriceDetailRowFields}totalItemQuantity fees{...PriceDetailRowFields}taxTotal{...PriceDetailRowFields}grandTotal{...PriceDetailRowFields}belowMinimumFee{...PriceDetailRowFields}authorizationAmount{...PriceDetailRowFields}weightDebitTotal{...PriceDetailRowFields}discounts{...PriceDetailRowFields}otcDeliveryBenefit{...PriceDetailRowFields}ebtSnapMaxEligible{...PriceDetailRowFields}ebtCashMaxEligible{...PriceDetailRowFields}originalSubTotal{...PriceDetailRowFields}savedPriceSubTotal{...PriceDetailRowFields}hasGrandTotalChanged hasAmountUnallocated hadMinThresholdFeeDuringPCCreation affirm{__typename message{...AffirmMessageFields}}rewardsEligibility{...RewardsEligibilityFields}}checkoutGiftingDetails{isCheckoutGiftingOptin isWalmartProtectionPlanPresent isAppleCarePresent isRestrictedPaymentPresent giftMessageDetails{giftingMessage recipientEmail recipientName senderName}}promotions @include(if:$promosEnable){displayValue promoId terms}serverTime showPromotions @include(if:$promosEnable)...ContractErrorsFields substitutionSummary{...SubstitutionSummaryFragment}}fragment LineItemFields on LineItem{id quantity quantityString quantityLabel accessibilityQuantityLabel isWplusEarlyAccess isEventActive needsPrescription eventType fulfillmentSourcingDetails{currentSelection requestedSelection}packageQuantity personalizedItemDetails{personalizedConfigID personalizedConfigAttributes{name value}}priceInfo{priceDisplayCodes{showItemPrice priceDisplayCondition finalCostByWeight}itemPrice{displayValue value}linePrice{displayValue value}preDiscountedLinePrice{displayValue value}wasPrice{displayValue value}unitPrice{displayValue value}savedPrice{displayValue value}}isSubstitutionSelected isGiftEligible expiresAt showExpirationTimer selectedVariants{name value}product{...ProductFields}discounts{key label value @include(if:$promosEnable) terms subType displayValue @include(if:$promosEnable) displayLabel}wirelessPlan{planId mobileNumber __typename postPaidPlan{...postpaidPlanDetailsFragment}}selectedAddOnServices{offerId quantity groupType}registryInfo{registryId registryType}}fragment postpaidPlanDetailsFragment on PostPaidPlan{__typename espOrderSummaryId espOrderId espOrderLineId warpOrderId warpSessionId devicePayment{...postpaidPlanPriceFragment}devicePlan{__typename price{...postpaidPlanPriceFragment}frequency duration annualPercentageRate}deviceDataPlan{...deviceDataPlanFragment}}fragment deviceDataPlanFragment on DeviceDataPlan{__typename carrierName planType expiryTime activationFee{...postpaidPlanPriceFragment}planDetails{__typename price{...postpaidPlanPriceFragment}frequency name}agreements{...agreementFragment}}fragment postpaidPlanPriceFragment on PriceDetailRow{__typename key label displayValue value strikeOutDisplayValue strikeOutValue info{__typename title message}}fragment agreementFragment on CarrierAgreement{__typename name type format value docTitle label}fragment preOrderFragment on PreOrder{streetDate isPreOrder}fragment AddressFields on Address{id addressLineOne addressLineTwo city state postalCode firstName lastName phone}fragment PickupPersonFields on PickupPerson{id firstName lastName email}fragment PriceDetailRowFields on PriceDetailRow{__typename key label displayValue value strikeOutValue strikeOutDisplayValue additionalInfo info{__typename title message}program @include(if:$enableWalmartPlusFreeDiscountedExpress)}fragment AccessPointFields on AccessPoint{id name assortmentStoreId displayName timeZone address{id addressLineOne addressLineTwo city state postalCode firstName lastName phone}isTest allowBagFee bagFeeValue isExpressEligible cartFulfillmentOption instructions nodeAccessType}fragment ReservationFields on Reservation{id expiryTime isUnscheduled expired showSlotExpiredError reservedSlot{__typename...on RegularSlot{id price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId cartFulfillmentOption startTime fulfillmentType nodeAccessType slotMetadata slotExpiryTime endTime available supportedTimeZone isPopular}...on DynamicExpressSlot{id price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId cartFulfillmentOption startTime endTime fulfillmentType nodeAccessType slotMetadata slotExpiryTime available slaInMins sla{value displayValue}maxItemAllowed supportedTimeZone}...on UnscheduledSlot{price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId cartFulfillmentOption startTime fulfillmentType nodeAccessType slotMetadata unscheduledHoldInDays supportedTimeZone}...on InHomeSlot{id price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId cartFulfillmentOption startTime fulfillmentType nodeAccessType slotMetadata slotExpiryTime endTime available supportedTimeZone}}}fragment AffirmMessageFields on AffirmMessage{__typename description termsUrl imageUrl monthlyPayment termLength isZeroAPR}fragment FulfillmentItemGroupsFields on FulfillmentItemGroup{...on SCGroup{__typename defaultMode collapsedItemIds itemGroups{__typename label itemIds}accessPoint{...AccessPointFields}reservation{...ReservationFields}pickupLocationCount}...on DigitalDeliveryGroup{__typename defaultMode collapsedItemIds itemGroups{__typename label itemIds}}...on Unscheduled{__typename defaultMode collapsedItemIds isSpecialEvent startDate endDate itemGroups{__typename label itemIds}accessPoint{...AccessPointFields}reservation{...ReservationFields}}...on MPGroup{__typename defaultMode collapsedItemIds startDate endDate itemGroups{__typename label itemIds}accessPoint{...AccessPointFields}reservation{...ReservationFields}}...on FCGroup{__typename defaultMode collapsedItemIds startDate endDate isUnscheduledDeliveryEligible shippingOptions{__typename itemIds availableShippingOptions{__typename id shippingMethod deliveryDate price{__typename displayValue value}label{prefix suffix}isSelected isDefault slaTier}}hasMadeShippingChanges slaGroups{__typename label deliveryDate warningLabel sellerGroups{__typename id name isProSeller type shipOptionGroup{__typename deliveryPrice{__typename displayValue value}itemIds shipMethod}}}}...on AutoCareCenter{__typename defaultMode startDate endDate accBasketType collapsedItemIds itemGroups{__typename label itemIds}accessPoint{...AccessPointFields}reservation{...ReservationFields}accFulfillmentGroups @include(if:$isACCEnabled){...ACCFulfillmentItemGroupFields}}}fragment ACCFulfillmentItemGroupFields on ACCFulfillmentGroup{collapsedItemIds itemGroupType reservation{...ReservationFields}itemGroups{__typename label itemIds}}fragment ProductFields on Product{id name usItemId itemType imageInfo{thumbnailUrl}category{categoryPath categoryPathId}fulfillmentLabel @include(if:$enableFulfillmentLabels){checkStoreAvailability wPlusFulfillmentText message shippingText fulfillmentText locationText fulfillmentMethod addressEligibility fulfillmentType postalCode}offerId orderLimit orderMinLimit weightIncrement weightUnit averageWeight salesUnitType availabilityStatus isSubstitutionEligible isAlcohol configuration hasSellerBadge sellerId sellerName sellerType annualEvent personalizable preOrder{...preOrderFragment}badges{flags{__typename id key text}}addOnServices{serviceType groups{groupType services{selectedDisplayName offerId currentPrice{priceString}}}}type}fragment ContractErrorsFields on PurchaseContract{allocationStatus checkoutError{...CheckoutErrorField}}fragment CheckoutErrorField on CheckoutOperationalError{__typename code message errorData{...on OutOfStock{__typename offerId}...on UnavailableOffer{__typename offerId}...on ItemQuantityAdjusted{__typename offerId requestedQuantity adjustedQuantity}...on ItemExpired{__typename offerId}...on AppointmentExpired{__typename offerId}}operationalErrorCode errorLineItems{...CheckoutErrorLineItemsField}}fragment CheckoutErrorLineItemsField on CheckoutOperationalErrorLineItem{__typename offerId usItemId product{...ProductFields}lineItem{...LineItemFields}}fragment RewardsEligibilityFields on RewardsEligibilityInfo{paymentType cardType preferenceId balance{displayValue value}}fragment SubstitutionSummaryFragment on SubstitutionSummary{hasSubstitutionEligibleItems hasItemsWithSubstitutionPreference}",
		    "variables": {
		        "enableWalmartPlusFreeDiscountedExpress": False,
		        "isACCEnabled": True,
		        "onlyFetchCheckoutErrors": False,
		        "placeOrderInput": {
		            "acceptAlcoholDisclosure": None,
		            "acceptBagFee": None,
		            "acceptDonation": False,
		            "acceptSMSOptInDisclosure": None,
		            "acceptedAgreements": [],
		            "contractId": contract_id,
		            "deliveryDetails": None,
		            "emailAddress": self.profile["email"],
		            "fulfillmentOptions": None,
		            "marketingEmailPref": None,
		            "mobileNumber": None,
		            "paymentCvvInfos": [self.cvv_verify],
		            "paymentHandle": None,
		            "substitutions": [
		                {
		                    "isSubstitutionSelected": False,
		                    "purchaseLineItemId": ipurchase_id,
		                }
		            ]
		        },
		        "promosEnable": True,
		        "wplusEnabled": True
		    }
		}

		if self.pickup_type != "PICKUP":
			b["variables"]["placeOrderInput"]["tipAmount"] = 4
			b["variables"]["placeOrderInput"]["deliveryDetails"] = {"deliveryInstructions": None, "deliveryOption": "MEET_AT_DOOR"}
			b["variables"]["placeOrderInput"]["acceptedAgreements"] = []
		header = {'pragma': 'no-cache', 'cache-control': 'no-cache', 'x-o-platform': 'rweb', 'dnt': '1', 'x-o-correlation-id': 'L5CMp5QQg3vIhx0EDpSHLgC05e36fdqLJowf', 'device_profile_ref_id': 'e1iNk50EP8XaY_1tquXG9RhK6qqTYTI9NKvZ', 'x-latency-trace': '1', 'wm_mp': 'true', 'x-o-market': 'us', 'x-o-platform-version': 'main-420-626f2c', 'x-o-gql-query': 'mutation PlaceOrder', 'x-apollo-operation-name': 'PlaceOrder', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36', 'x-o-segment': 'oaoh', 'content-type': 'application/json', 'accept': 'application/json', 'x-enable-server-timing': '1', 'x-o-ccm': 'server', 'x-o-tp-phase': 'tp5', 'wm_qos.correlation_id': 'L5CMp5QQg3vIhx0EDpSHLgC05e36fdqLJowf', 'origin': 'https', 'sec-fetch-site': 'same-origin', 'sec-fetch-mode': 'cors', 'sec-fetch-dest': 'empty', 'referer': 'https', 'accept-encoding': 'gzip, deflate, br', 'accept-language': 'en-US,en;q=0.9,fr;q=0.8,ar;q=0.7'}
		header["referer"] = self.referer
		# header["origin"] = "https://www.walmart.com"
		self.status_signal.emit({"msg": "Submitting Order", "status": "alt"})
		r = self.session.post("https://www.walmart.com/orchestra/cartxo/graphql", data=json.dumps(b), headers=header)
		
		if self.is_captcha(r.text):
			raise captchaExp()
		
		data = json.loads(r.text)
		if r.headers["X-Auth-Status"] == "passed":
			self.status_signal.emit({"msg": "Order placed", "status": "normal"})
			return {"success": True }
		else:
			self.status_signal.emit({"msg": "Error Submitting Order", "status": "error"})
			try:
				
				if data["errors"][0]["message"] == "Purchase Contract has expired. Create a new Purchase Contract":
					self.status_signal.emit({"msg": "Purchase Contract is expired" , "status": "error"})
				
				self.status_signal.emit({"msg": data["errors"][0]["extensions"]["exception"]["message"] , "status": "error"})
				return {"success": False, "message": "error :" + str(data["errors"][0]["extensions"]["exception"]["message"]), "log" : {}}
			except:
				raise Internalexp()
				# self.set_shipping() #can call place order in a recursive way creating a infinte loop will do for now
				# return self.submit_order(contract_id, ipurchase_id)

	@safe_execute
	def get_stores(self):
		b = {
		   "query":"query nearByNodes($input:LocationInput! $checkItemAvailability:Boolean!){nearByNodes(input:$input){nodes{id distance type isGlassEligible displayName name address{addressLineOne addressLineTwo state city postalCode country}geoPoint @skip(if:$checkItemAvailability){latitude longitude}capabilities{accessPointId accessPointType geoPoint @skip(if:$checkItemAvailability){latitude longitude}expressEnabled bagFeeDetails @skip(if:$checkItemAvailability){isBagFeeEligible bagFee{displayValue value}}isActive isTest assortmentNodeId tippingEnabled acceptsEbt isMembershipEnabled timeZone}open24Hours displayAccessTypes isNodeSelectableOnline operationalHours{day start closed end}product @include(if:$checkItemAvailability){availabilityStatus}}}}",
		   "variables":{
			  "input":{
				 "postalCode":self.profile["postalCode"],
				 "accessTypes":[
					"PICKUP_INSTORE",
					"PICKUP_CURBSIDE"
				 ],
				 "nodeTypes":None,
				 "latitude":None,
				 "longitude":None,
				 "radius":None
			  },
			  "checkItemAvailability":False
		   }
		}
		self.header["x-o-gql-query"] = "query nearByNodes"
		self.header["x-apollo-operation-name"] = "nearByNodes"
		r = self.session.post("https://www.walmart.com/orchestra/cartxo/graphql", data=json.dumps(b), headers=self.header)
		if self.is_captcha(r.text):
			raise captchaExp()
		data = json.loads(r.text)
		return data["data"]["nearByNodes"]["nodes"]

	@safe_execute
	def get_shipping_info(self, intent):
		self.status_signal.emit({"msg": "setting shipping info", "status": "normal"})
		stores = self.get_stores()
		for store in stores:
			b2 = {
			   "query":"mutation setPickup( $input:SetFulfillmentPickupInput! $includePartialFulfillmentSwitching:Boolean! = false $enableAEBadge:Boolean! = false $includeQueueing:Boolean! = false $includeExpressSla:Boolean! = false $enableACCScheduling:Boolean! = false ){fulfillmentMutations{setPickup(input:$input){...CartFragment}}}fragment CartFragment on Cart{id checkoutable customer{id isGuest}cartGiftingDetails{isGiftOrder hasGiftEligibleItem isAddOnServiceAdjustmentNeeded isWalmartProtectionPlanPresent isAppleCarePresent}addressMode migrationLineItems{quantity quantityLabel quantityString accessibilityQuantityLabel offerId usItemId productName thumbnailUrl addOnService priceInfo{linePrice{value displayValue}}selectedVariants{name value}}lineItems{id quantity quantityString quantityLabel hasShippingRestriction isPreOrder isGiftEligible isSubstitutionSelected displayAddOnServices createdDateTime discounts{key displayValue displayLabel value terms subType}isWplusEarlyAccess isEventActive eventType selectedAddOnServices{offerId quantity groupType isGiftEligible error{code upstreamErrorCode errorMsg}}bundleComponents{offerId quantity product{name usItemId imageInfo{thumbnailUrl}}}registryId fulfillmentPreference selectedVariants{name value}priceInfo{priceDisplayCodes{showItemPrice priceDisplayCondition finalCostByWeight}itemPrice{...lineItemPriceInfoFragment}wasPrice{...lineItemPriceInfoFragment}unitPrice{...lineItemPriceInfoFragment}linePrice{...lineItemPriceInfoFragment}}product{id name usItemId sponsoredProduct{spQs clickBeacon spTags}sellerDisplayName fulfillmentBadge variants{availabilityStatus}seller{name sellerId}imageInfo{thumbnailUrl}addOnServices{serviceType serviceTitle serviceSubTitle groups{groupType groupTitle assetUrl shortDescription services{displayName selectedDisplayName offerId usItemId currentPrice{priceString price}serviceMetaData giftEligible}}}itemType offerId sellerId sellerName hasSellerBadge orderLimit orderMinLimit weightUnit weightIncrement salesUnit salesUnitType sellerType isAlcohol fulfillmentType fulfillmentSpeed fulfillmentTitle classType rhPath availabilityStatus brand category{categoryPath}departmentName configuration snapEligible preOrder{isPreOrder}badges @include(if:$enableAEBadge){...BadgesFragment}shippingOption{shipPrice{priceString}}}registryInfo{registryId registryType}wirelessPlan{planId mobileNumber postPaidPlan{...postpaidPlanDetailsFragment}}fulfillmentSourcingDetails{currentSelection requestedSelection fulfillmentBadge}availableQty expiresAt @include(if:$includeQueueing) showExpirationTimer @include(if:$includeQueueing)}fulfillment{intent accessPoint{...accessPointCartFragment}reservation{...reservationFragment}storeId displayStoreSnackBarMessage homepageBookslotDetails{title subTitle expiryText expiryTime slotExpiryText}deliveryAddress{addressLineOne addressLineTwo city state postalCode firstName lastName id phone}fulfillmentItemGroups{...on FCGroup{__typename defaultMode collapsedItemIds startDate endDate checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...priceTotalFields}}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}shippingOptions{__typename itemIds availableShippingOptions{__typename id shippingMethod deliveryDate price{__typename displayValue value}label{prefix suffix}isSelected isDefault slaTier}}hasMadeShippingChanges slaGroups{__typename label deliveryDate sellerGroups{__typename id name isProSeller type catalogSellerId shipOptionGroup{__typename deliveryPrice{__typename displayValue value}itemIds shipMethod}}warningLabel}}...on SCGroup{__typename defaultMode collapsedItemIds checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...priceTotalFields}}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}itemGroups{__typename label itemIds accessPoint{...accessPointCartFragment}}accessPoint{...accessPointCartFragment}reservation{...reservationFragment}}...on DigitalDeliveryGroup{__typename defaultMode collapsedItemIds checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...priceTotalFields}}itemGroups{__typename label itemIds accessPoint{...accessPointCartFragment}}}...on Unscheduled{__typename defaultMode collapsedItemIds checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...priceTotalFields}}itemGroups{__typename label itemIds accessPoint{...accessPointCartFragment}}accessPoint{...accessPointCartFragment}reservation{...reservationFragment}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}isSpecialEvent @include(if:$enableAEBadge)}...on AutoCareCenter{__typename defaultMode collapsedItemIds startDate endDate accBasketType checkoutable checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}priceDetails{subTotal{...priceTotalFields}}itemGroups{__typename label itemIds accessPoint{...accessPointCartFragment}}accFulfillmentGroups @include(if:$enableACCScheduling){collapsedItemIds itemGroupType reservation{...reservationFragment}suggestedSlotAvailability{...suggestedSlotAvailabilityFragment}itemGroups{__typename label itemIds}}accessPoint{...accessPointCartFragment}reservation{...reservationFragment}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}}}suggestedSlotAvailability{...suggestedSlotAvailabilityFragment}}priceDetails{subTotal{...priceTotalFields}fees{...priceTotalFields}taxTotal{...priceTotalFields}grandTotal{...priceTotalFields}belowMinimumFee{...priceTotalFields}minimumThreshold{value displayValue}ebtSnapMaxEligible{displayValue value}balanceToMinimumThreshold{value displayValue}totalItemQuantity}affirm{isMixedPromotionCart message{description termsUrl imageUrl monthlyPayment termLength isZeroAPR}nonAffirmGroup{...nonAffirmGroupFields}affirmGroups{...on AffirmItemGroup{__typename message{description termsUrl imageUrl monthlyPayment termLength isZeroAPR}flags{type displayLabel}name label itemCount itemIds defaultMode}}}checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}checkoutableWarnings{code itemIds}operationalErrors{offerId itemId requestedQuantity adjustedQuantity code upstreamErrorCode}cartCustomerContext{...cartCustomerContextFragment}}fragment postpaidPlanDetailsFragment on PostPaidPlan{espOrderSummaryId espOrderId espOrderLineId warpOrderId warpSessionId isPostpaidExpired devicePayment{...postpaidPlanPriceFragment}devicePlan{price{...postpaidPlanPriceFragment}frequency duration annualPercentageRate}deviceDataPlan{...deviceDataPlanFragment}}fragment deviceDataPlanFragment on DeviceDataPlan{carrierName planType expiryTime activationFee{...postpaidPlanPriceFragment}planDetails{price{...postpaidPlanPriceFragment}frequency name}agreements{...agreementFragment}}fragment postpaidPlanPriceFragment on PriceDetailRow{key label displayValue value strikeOutDisplayValue strikeOutValue info{title message}}fragment agreementFragment on CarrierAgreement{name type format value docTitle label}fragment priceTotalFields on PriceDetailRow{label displayValue value key strikeOutDisplayValue strikeOutValue}fragment lineItemPriceInfoFragment on Price{displayValue value}fragment accessPointCartFragment on AccessPoint{id assortmentStoreId name nodeAccessType accessType fulfillmentType fulfillmentOption displayName timeZone bagFeeValue isActive address{addressLineOne addressLineTwo city postalCode state phone}}fragment suggestedSlotAvailabilityFragment on SuggestedSlotAvailability{isPickupAvailable isDeliveryAvailable nextPickupSlot{startTime endTime slaInMins}nextDeliverySlot{startTime endTime slaInMins}nextUnscheduledPickupSlot{startTime endTime slaInMins}nextSlot{__typename...on RegularSlot{fulfillmentOption fulfillmentType startTime}...on DynamicExpressSlot{fulfillmentOption fulfillmentType startTime slaInMins sla{value displayValue}}...on UnscheduledSlot{fulfillmentOption fulfillmentType startTime unscheduledHoldInDays}...on InHomeSlot{fulfillmentOption fulfillmentType startTime}}}fragment reservationFragment on Reservation{expiryTime isUnscheduled expired showSlotExpiredError reservedSlot{__typename...on RegularSlot{id price{total{value displayValue}expressFee{value displayValue}baseFee{value displayValue}memberBaseFee{value displayValue}}nodeAccessType accessPointId fulfillmentOption startTime fulfillmentType slotMetadata endTime available supportedTimeZone isAlcoholRestricted}...on DynamicExpressSlot{id price{total{value displayValue}expressFee{value displayValue}baseFee{value displayValue}memberBaseFee{value displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata available sla @include(if:$includeExpressSla){value displayValue}slaInMins maxItemAllowed supportedTimeZone isAlcoholRestricted}...on UnscheduledSlot{price{total{value displayValue}expressFee{value displayValue}baseFee{value displayValue}memberBaseFee{value displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata unscheduledHoldInDays supportedTimeZone}...on InHomeSlot{id price{total{value displayValue}expressFee{value displayValue}baseFee{value displayValue}memberBaseFee{value displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata endTime available supportedTimeZone isAlcoholRestricted}}}fragment nonAffirmGroupFields on NonAffirmGroup{label itemCount itemIds collapsedItemIds}fragment cartCustomerContextFragment on CartCustomerContext{isMembershipOptedIn isEligibleForFreeTrial membershipData{isActiveMember isPaidMember}paymentData{hasCreditCard hasCapOne hasDSCard hasEBT isCapOneLinked showCapOneBanner}}fragment BadgesFragment on UnifiedBadge{flags{__typename...on BaseBadge{id text key query}...on PreviouslyPurchasedBadge{id text key lastBoughtOn numBought criteria{name value}}}labels{__typename...on BaseBadge{id text key}...on PreviouslyPurchasedBadge{id text key lastBoughtOn numBought}}tags{__typename...on BaseBadge{id text key}...on PreviouslyPurchasedBadge{id text key}}}",
			   "variables":{
				  "input":{
					 "accessPointId": store["capabilities"][0]["accessPointId"],
					 "cartId": self.cart_id,
					 "postalCode": self.profile["postalCode"],
					 "storeId": int(store["id"])
				  },
				  "includePartialFulfillmentSwitching":True,
				  "enableAEBadge":True,
				  "includeExpressSla":True,
				  "includeQueueing":True,
				  "enableACCScheduling":False
			   }
			} 
			self.header["x-o-gql-query"] = "mutation setPickup"
			self.header["x-apollo-operation-name"] = "setPickup"
			r1 = self.session.post("https://www.walmart.com/orchestra/cartxo/graphql", data=json.dumps(b2), headers=self.header)
			if self.is_captcha(r1.text):
				raise captchaExp()
			data1 = json.loads(r1.text)
			
			slots = self.get_slots(intent)
			for slot in slots:
					if slot["hasAvailableSlots"]:
						for day in slot["eachDaySlots"]:
							if day["available"]:
								self.status_signal.emit({"msg": "found pickup/shipping date", "status": "normal"})
								return day["slotMetadata"] 
		else:
			return False

	@safe_execute
	def set_shipping(self):
		self.status_signal.emit({"msg": "setting shipping", "status": "normal"})
		lineitems = self.get_cart()
		fbadge = lineitems[0]["fulfillmentSourcingDetails"]["fulfillmentBadge"]   
		if "SHIPPING_ONLY" in fbadge:
			self.status_signal.emit({"msg": "element is set to shipping only", "status": "normal"})
			slot_meta = self.get_shipping_info("DELIVERY")
			self.pickup_type = "SHIPPING"
			if not slot_meta:
				self.status_signal.emit({"msg": "element is set to shipping only yet found no available shipping date", "status": "normal"})

		else:
			self.status_signal.emit({"msg": "searching for pickup slot", "status": "normal"})
			slot_meta = self.get_shipping_info("PICKUP")
			self.pickup_type = "PICKUP"
			if not slot_meta:
				self.status_signal.emit({"msg": "found no available pickup slot trying delivery instead", "status": "normal"})
				slot_meta = self.get_shipping_info("DELIVERY")
				self.pickup_type = "SHIPPING"
				if not slot_meta:
					self.status_signal.emit({"msg": "found no available pickup nor delivery ", "status": "normal"})


		self.header["x-o-gql-query"] = "mutation reserveSlotMutation"
		self.header["x-apollo-operation-name"] = "reserveSlotMutation"
		self.header["referer"] = "https://www.walmart.com/?step=bookslot"
		self.header["wm_page_url"] = "https://www.walmart.com/?step=bookslot"
		b = {
		   "query":"mutation reserveSlotMutation( $cartId:ID! $slotMetadata:String! $includePartialFulfillmentSwitching:Boolean! = false $enableAEBadge:Boolean! = false $includeQueueing:Boolean! = false $includeExpressSla:Boolean! = false $enableACCScheduling:Boolean! = false ){reserveSlot(input:{cartId:$cartId slotMetadata:$slotMetadata}){id checkoutable customer{id firstName lastName isGuest}cartGiftingDetails{isGiftOrder hasGiftEligibleItem isAddOnServiceAdjustmentNeeded isWalmartProtectionPlanPresent isAppleCarePresent}addressMode migrationLineItems{quantity quantityLabel quantityString accessibilityQuantityLabel offerId usItemId productName thumbnailUrl addOnService priceInfo{linePrice{value displayValue}}selectedVariants{name value}}lineItems{id quantity quantityString quantityLabel isPreOrder isGiftEligible isWplusEarlyAccess isEventActive eventType selectedAddOnServices{offerId quantity groupType isGiftEligible error{code upstreamErrorCode errorMsg}}createdDateTime bundleComponents{offerId quantity}registryInfo{registryId registryType}selectedVariants{name value}registryId fulfillmentPreference priceInfo{priceDisplayCodes{showItemPrice priceDisplayCondition finalCostByWeight}itemPrice{...lineItemPriceInfoFragment}wasPrice{...lineItemPriceInfoFragment}unitPrice{...lineItemPriceInfoFragment}linePrice{...lineItemPriceInfoFragment}}product{name usItemId imageInfo{thumbnailUrl}addOnServices{serviceType serviceTitle serviceSubTitle groups{groupType groupTitle assetUrl shortDescription services{displayName selectedDisplayName offerId currentPrice{priceString price}serviceMetaData giftEligible}}}itemType offerId orderLimit orderMinLimit weightUnit weightIncrement salesUnit salesUnitType isAlcohol fulfillmentType fulfillmentSpeed fulfillmentTitle classType rhPath availabilityStatus brand category{categoryPath}departmentName configuration snapEligible preOrder{isPreOrder}badges @include(if:$enableAEBadge){...BadgesFragment}}wirelessPlan{planId mobileNumber postPaidPlan{...postpaidPlanDetailsFragment}}fulfillmentSourcingDetails{currentSelection requestedSelection fulfillmentBadge}expiresAt @include(if:$includeQueueing) showExpirationTimer @include(if:$includeQueueing)}fulfillment{intent storeId displayStoreSnackBarMessage homepageBookslotDetails{title subTitle expiryText expiryTime slotExpiryText}deliveryAddress{addressLineOne addressLineTwo city state postalCode firstName lastName id}accessPoint{...accessPointFragment}reservation{...reservationFragment}fulfillmentItemGroups{...on FCGroup{__typename defaultMode collapsedItemIds startDate endDate checkoutable priceDetails{subTotal{...priceTotalFields}}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}shippingOptions{__typename itemIds availableShippingOptions{__typename id shippingMethod deliveryDate price{__typename displayValue value}label{prefix suffix}isSelected isDefault slaTier}}hasMadeShippingChanges slaGroups{__typename label sellerGroups{__typename id name isProSeller type catalogSellerId shipOptionGroup{__typename deliveryPrice{__typename displayValue value}itemIds shipMethod}}warningLabel}}...on SCGroup{__typename defaultMode collapsedItemIds checkoutable priceDetails{subTotal{...priceTotalFields}}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}itemGroups{__typename label itemIds}accessPoint{...accessPointFragment}reservation{...reservationFragment}}...on DigitalDeliveryGroup{__typename defaultMode collapsedItemIds checkoutable priceDetails{subTotal{...priceTotalFields}}itemGroups{__typename label itemIds}}...on Unscheduled{__typename defaultMode collapsedItemIds checkoutable priceDetails{subTotal{...priceTotalFields}}itemGroups{__typename label itemIds}accessPoint{...accessPointFragment}reservation{...reservationFragment}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}isSpecialEvent @include(if:$enableAEBadge)}...on AutoCareCenter{__typename defaultMode collapsedItemIds startDate endDate accBasketType checkoutable priceDetails{subTotal{...priceTotalFields}}itemGroups{__typename label itemIds}accFulfillmentGroups @include(if:$enableACCScheduling){collapsedItemIds itemGroupType reservation{...reservationFragment}suggestedSlotAvailability{...suggestedSlotAvailabilityFragment}itemGroups{__typename label itemIds}}accessPoint{...accessPointFragment}reservation{...reservationFragment}fulfillmentSwitchInfo{fulfillmentType benefit{type price itemCount date isWalmartPlusProgram}partialItemIds @include(if:$includePartialFulfillmentSwitching)}}}suggestedSlotAvailability{...suggestedSlotAvailabilityFragment}}priceDetails{subTotal{...priceTotalFields}fees{...priceTotalFields}grandTotal{...priceTotalFields}belowMinimumFee{...priceTotalFields}minimumThreshold{value displayValue}taxTotal{...priceTotalFields}ebtSnapMaxEligible{displayValue value}}affirm{isMixedPromotionCart message{description termsUrl imageUrl monthlyPayment termLength isZeroAPR}nonAffirmGroup{...nonAffirmGroupFields}affirmGroups{...on AffirmItemGroup{__typename message{description termsUrl imageUrl monthlyPayment termLength isZeroAPR}flags{type displayLabel}name label itemCount itemIds defaultMode}}}checkoutableErrors{code shouldDisableCheckout itemIds upstreamErrors{offerId upstreamErrorCode}}checkoutableWarnings{code itemIds}operationalErrors{offerId itemId requestedQuantity adjustedQuantity code}cartCustomerContext{...cartCustomerContextFragment}}}fragment postpaidPlanDetailsFragment on PostPaidPlan{espOrderSummaryId espOrderId espOrderLineId warpOrderId warpSessionId devicePayment{...postpaidPlanPriceFragment}devicePlan{price{...postpaidPlanPriceFragment}frequency duration annualPercentageRate}deviceDataPlan{...deviceDataPlanFragment}}fragment deviceDataPlanFragment on DeviceDataPlan{carrierName planType expiryTime activationFee{...postpaidPlanPriceFragment}planDetails{price{...postpaidPlanPriceFragment}frequency name}agreements{...agreementFragment}}fragment postpaidPlanPriceFragment on PriceDetailRow{key label displayValue value strikeOutDisplayValue strikeOutValue info{title message}}fragment agreementFragment on CarrierAgreement{name type format value docTitle label}fragment priceTotalFields on PriceDetailRow{label displayValue value key strikeOutDisplayValue strikeOutValue}fragment lineItemPriceInfoFragment on Price{displayValue value}fragment accessPointFragment on AccessPoint{id assortmentStoreId name nodeAccessType fulfillmentType fulfillmentOption displayName timeZone address{addressLineOne addressLineTwo city postalCode state phone}}fragment suggestedSlotAvailabilityFragment on SuggestedSlotAvailability{isPickupAvailable isDeliveryAvailable nextPickupSlot{available startTime endTime slaInMins}nextDeliverySlot{available startTime endTime slaInMins}nextUnscheduledPickupSlot{available startTime endTime slaInMins}nextSlot{__typename...on RegularSlot{fulfillmentType available startTime}...on DynamicExpressSlot{fulfillmentType available startTime slaInMins}...on UnscheduledSlot{fulfillmentType startTime unscheduledHoldInDays}}}fragment reservationFragment on Reservation{expiryTime isUnscheduled expired showSlotExpiredError reservedSlot{__typename...on RegularSlot{id price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata endTime available supportedTimeZone isAlcoholRestricted}...on DynamicExpressSlot{id price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata available sla @include(if:$includeExpressSla){value displayValue}slaInMins maxItemAllowed supportedTimeZone isAlcoholRestricted}...on UnscheduledSlot{price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata unscheduledHoldInDays supportedTimeZone}...on InHomeSlot{id price{total{displayValue}expressFee{displayValue}baseFee{displayValue}memberBaseFee{displayValue}}accessPointId fulfillmentOption startTime fulfillmentType slotMetadata endTime available supportedTimeZone isAlcoholRestricted}}}fragment nonAffirmGroupFields on NonAffirmGroup{label itemCount itemIds collapsedItemIds}fragment cartCustomerContextFragment on CartCustomerContext{isMembershipOptedIn isEligibleForFreeTrial membershipData{isActiveMember}paymentData{hasCreditCard hasCapOne hasDSCard hasEBT isCapOneLinked showCapOneBanner}}fragment BadgesFragment on UnifiedBadge{flags{__typename...on BaseBadge{id text key query}...on PreviouslyPurchasedBadge{id text key lastBoughtOn numBought criteria{name value}}}labels{__typename...on BaseBadge{id text key}...on PreviouslyPurchasedBadge{id text key lastBoughtOn numBought}}tags{__typename...on BaseBadge{id text key}}}",
		   "variables":{
			  "cartId": self.cart_id,
			  "slotMetadata": slot_meta,
			  "includePartialFulfillmentSwitching":True,
			  "enableAEBadge":True,
			  "includeQueueing":True,
			  "includeExpressSla":True,
			  "enableACCScheduling":False
		   }
		}

		r = self.session.post("https://www.walmart.com/orchestra/cartxo/graphql", data=json.dumps(b), headers=self.header)
		if self.is_captcha(r.text):
			raise captchaExp()
		data = json.loads(r.text)
		if r.status_code == 200:
			self.status_signal.emit({"msg": "shipping was set", "status": "normal"})

	@safe_execute
	def handle_captcha(self, driver=False, close=True): 
		# this opens up chrome browser to get prompted with captcha
		self.status_signal.emit({"msg": "handling captcha", "status": "normal"})
		if not driver:
			chrome_options = Options()  
			chrome_options.add_argument('--proxy-server=localhost:8080')
			driver = webdriver.Chrome(options=chrome_options)
			
			driver.get("https://www.walmart.com") #we are loading cookies so if user is logged in we dont overwrite them with cookies in wich he is not logged in also 
			try:	
				cookies = self.supabase.table("walmart_cookies").select(
							"data").match(dict(owner=self.userid)).execute()
				cookies = cookies.data[0]["data"]
			except:
				pass
			else:
				self.load_cookies(driver)

		j = 0
		# driver.get("https://www.walmart.com")
		# time.sleep(2)
		f = AnyEc()
		while(True):
			driver.get("https://www.walmart.com")
			try:
				f.wait_for_element(driver, "px-captcha", 10)
			except:
				pass
			if self.is_captcha(driver.page_source):
				self.status_signal.emit({"msg": "captcha found", "status": "normal"})
				found = False
				try:
					driver.find_elements(By.XPATH, "//*[contains(text(), 'Try a different method')]")[0].click()
					found = True
				except:
					try:
						driver.find_elements(By.XPATH, 'w_AC w_AG w_AI')[0].click()
						found = True
					except Exception as ex:
						print(ex)
						self.status_signal.emit({"msg": "error finding captcha", "status": "error"})
						if self.debug:
							code.interact(local=locals())
						break
				if found:
					try:
						f.wait_for_element_by_class(driver, "g-recaptcha")
					except:
						self.status_signal.emit({"msg": "captcha took too long to load reloading page", "status": "normal"})
						continue
					try:
						grep = driver.find_elements(By.XPATH, '//*[@id="px-captcha"]/div')[0]
					except:
						print("error finding captcha info")
						if self.debug:
							code.interact(local=locals())
					try:
						if self.debug:
							input("press enter when finish solving 1 captcha")
							
						else:
							result = self.solver.recaptcha(sitekey=grep.get_attribute("data-sitekey"),url=driver.current_url)
					except Exception as ex :
						try:
							result = self.solver.recaptcha(sitekey=grep.get_attribute("data-sitekey"),url=driver.current_url)
						except:
							print(ex)
							raise Internalexp({"message": "error trying to send captcha info to 2cap"})
					if not self.debug:
						# print(result["code"])  
						driver.execute_script('handleCaptcha(arguments[0])', result["code"])
						self.status_signal.emit({"msg": "captcha injected to website", "status": "normal"})
						j += 1


			elif j == 6:
				self.status_signal.emit({"msg": "walmart keeps blocking requests, sleeping", "status": "normal"})
				# raise Internalexp({"message": "captcha has been solved 5 times and access is still blocked"}) 
				time.sleep(60)
				j = 0


			else:
				self.status_signal.emit({"msg": "requests no longer blocked, proceeding", "status": "normal"})
				# code.interact(local=locals())
				cookies = driver.get_cookies()
				self.update_cookies(cookies, True) #no need to update driver cookies cause they already there since its same driver as login
				if close:
					driver.quit()
				return 

	def update_cookies(self, cookies, up_session=False):
		# self.session.cookies.clear()
		# if self.debug:
		# 	fp = open(os.path.join(os.path.expanduser('~')) + "/Onedrive/Bureau/walmart_cookies.txt", "w+")
		# 	json.dump(cookies, fp)
		# 	fp.close()
		# 	pass
		# else:
		try:#creates a new row if user dosent have a row already
			self.supabase.table("walmart_cookies").update({"data": json.dumps(cookies)}).match({"owner": str(self.userid)}).execute().data[0]["data"]
		except Exception as ex:#else modifys the existing row 
			print("exception at line 844 user has no saved cookies")
			self.supabase.table("walmart_cookies").insert({"owner": str(self.userid), "data": json.dumps(cookies)}).execute()
		
		if up_session:
			print("adding cookies to session")
			self.session.cookies.clear()
			for cookie in cookies:
				self.session.cookies.set(cookie["name"], cookie["value"])

	def load_cookies(self, driver=False, close=True):		
		try:
			cookies = self.supabase.table("walmart_cookies").select(
							"data").match(dict(owner=self.userid)).execute()
			cookies = cookies.data[0]["data"]
		except Exception as ex:
			print("exception in load_cookies", ex)
			self.handle_captcha(driver, close)
		else:
			cook = json.loads(cookies)
			self.session.cookies.clear()
			for j in cook:
				self.session.cookies.set(j["name"], j["value"])
				if driver:
					driver.add_cookie(j)

	def is_captcha(self, text):
		return ('<div class="re-captcha">' in text or "blocked?url=Lw" in text or "px-captcha" in text)

	@safe_execute
	def login(self):
		try:
			cookies = self.supabase.table("walmart_cookies").select(
							"data").match(dict(owner=self.userid)).execute()
			cookies = cookies.data[0]["data"]
		except Exception as ex:
			print("exception at login", ex)
			print("user has no saved cookies ")
		else:
			self.load_cookies(False, True)
			r = self.session.get("https://www.walmart.com/wallet", headers=self.header)
			if self.is_captcha(r.text):
				print("old cookies are expired and captcha is pushed to them")
				raise captchaExp()
				
			try:
				mailreg = re.findall(r'"emailAddress":"(.*?)"', r.text)[0]
			except Exception as ex:
				print("Exception at login line 844", ex)
			else:
				if mailreg == self.profile["email"]:
					self.status_signal.emit({"msg": "Already Logged in", "status": "normal"})
					return
				else:
					print(mailreg)
					raise Internalexp({"message": "wrong cookies from another account are passed to this instance"})


		chrome_options = Options()  
		chrome_options.add_argument('--proxy-server=localhost:8080')
		driver = webdriver.Chrome(options=chrome_options)
		f = AnyEc()
		self.status_signal.emit({"msg": "Logging in", "status": "normal"})
		if self.debug:
			# code.interact(local=locals())
			pass
		while (True):
			driver.get("https://www.walmart.com/")
			if self.is_captcha(driver.page_source): #used to verify if access to walmart is blocked or not so we dont get a forced button clicked while logging in later
				self.handle_captcha(driver, False)

			driver.get("https://www.walmart.com/account/login?vid=oaoh&ref=domain")

			try:
				f.wait_for_page(driver, "Login", 10)
			except:
				try:
					driver.find_elements(By.XPATH, '//*[@id="__next"]/div[1]/div/div/div/div/main/div[2]/div[2]/section/div/div/h2')[0]
				except:
					print("welcome back text was not found")
					if self.debug:
						# code.interact(local=locals())
						pass
				else:#already logged in 
					print("already logged in")
					self.update_cookies(driver.get_cookies(), True)
					break
			try:
				time.sleep(2)
				driver.find_elements(By.XPATH, '//*[@id="email"]')[0].send_keys(self.profile["email"])
				driver.find_elements(By.XPATH, '//*[@id="password"]')[0].send_keys(self.profile["password"])
				a = driver.find_elements(By.XPATH, '//*[@id="sign-in-form"]/div[1]/div/button')[0]
				click(driver, a, 15, 11)
			except :
				driver.find_elements(By.XPATH, '//*[@id="email-split-screen"]')[0].send_keys(self.profile["email"])
				a = driver.find_elements(By.XPATH, '//*[@id="sign-in-with-email-validation"]/div[1]/div/button')[0]
				click(driver, a, 3, 9.25)
				time.sleep(1)
				try:
					time.sleep(2)
					driver.find_elements(By.XPATH, '//*[@id="sign-in-password-no-otp"]')[0].send_keys(self.profile["password"])
					a = driver.find_elements(By.XPATH, '//*[@id="sign-in-with-password-form"]/div[5]/button')[0]
					click(driver, a, 7, 6)
				except Exception as ex: #not always happens					
					print(ex)
					print("captcha error after submitting email")

			#no need to wait for captcha since it will showup even if its not visible on screen
			try:
				f.wait_for_page(driver, 'Manage Account - Home - Walmart.com', 10)
			except Exception as ex:
				print("exception at line 953")
				print(ex)
				if "Your password and email do not match. Please try again or" in driver.page_source:
					self.status_signal.emit({"msg": "wrong account credentials", "status": "error"})
					code.interact(local=locals())
					raise Internalexp({"message": "wrong account credentials"})

				if self.is_captcha(driver.page_source):
					self.status_signal.emit({"msg": "Captcha in page while logging in", "status": "normal"})
					self.handle_captcha(driver, False)
					
				
			else:
				self.status_signal.emit({"msg": "Logged in successful", "status": "normal"})
				self.update_cookies(driver.get_cookies(), True)
				break

		driver.quit()
				
	def check_capkey(self):
		try:
			self.solver.balance()
		except:
			return False
		else:
			return True

	def encrypt_cvv(self):
		card_type = self.profile["cardType"].lower()
		if ("american" in card_type) or ("express" in card_type):
			card_num = "378282246310005"
		else:
			card_num = "4111111111111111"
		return self.get_PIE(card_num)


# //*[@id="waiting-room"]/h1 waiting room xpath


class Stat:

	def emit(self, a):#can be used to implement a way to talk to api
		print(a["msg"])




