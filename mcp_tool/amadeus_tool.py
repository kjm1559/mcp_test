import os
import datetime
import requests
import json
import logging
from typing import Optional, Annotated
from pydantic import Field
logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s',datefmt = '%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
logger = logging.getLogger(__name__)

class amadeus_tools:
    def __init__(self):
        self.secret_key = os.environ.get('AMADEUS_SECRET_KEY')
        self.api_key = os.environ.get('AMADEUS_API_KEY')
        self.get_token_url = 'https://test.api.amadeus.com/v1/security/oauth2/token'
        self.access_token = ''
        self.access_token_time = datetime.datetime(1970,1,1)
        self.expires_in = 0
        self.url = {
            'airplan_by_schedule': "https://test.api.amadeus.com/v2/shopping/flight-offers",
            'airplan_by_origin': "https://test.api.amadeus.com/v1/shopping/flight-destinations",
            'hotel_by_city': "https://test.api.amadeus.com/v1/reference-data/locations/hotels/by-city",
            'hotel_offers': "https://test.api.amadeus.com/v3/shopping/hotel-offers",
        }

    def __get_access_token(self):
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {
            'grant_type':'client_credentials',
            'client_id': self.api_key, 
            'client_secret': self.secret_key,
        }
        response = requests.post(
            url=self.get_token_url,
            headers=headers, 
            data=data
        )
        try:
            json_parsed = json.loads(response.text)
            self.access_token = json_parsed['access_token']
            self.expires_in = json_parsed['expires_in']
            self.access_token_time = datetime.datetime.now()
        except BaseException as e:
            logger.error(f'Fail getting acess token: {e}')
    
    def __check_access_token(self):
        if self.access_token == '' or \
            datetime.datetime.now() - self.access_token_time > datetime.timedelta(seconds=self.expires_in):
            self.__get_access_token()
    
    def __request_api(self, url:str, args:dict) -> requests.Response:
        if 'self' in args:
            args.pop('self')
        params = {key: args[key] for key in args if args[key] and args[key] != 'None' and callable(args[key]) == False}
        logger.info(f'param : {params}')
        self.__check_access_token()
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        response = requests.get(
            url=url,
            headers=headers,
            params=params,
        )
        return response

    def __search_parser(self, res: dict) -> dict:
        offers = []
        print('data', res)
        for o in res['data']:
            # Base information
            offer_id = o['id']
            carrier_code = o['validatingAirlineCodes'][0]
            carrier = res['dictionaries']['carriers'].get(carrier_code, 'N/A')
            ac_code = o['itineraries'][0]['segments'][0]['aircraft']['code']
            aircraft = res['dictionaries']['aircraft'][ac_code]
            
            # dep/ret schedule
            dep = o['itineraries'][0]['segments'][0]
            ret = o['itineraries'][1]['segments'][0]

            via_flag = False
            if len(o['itineraries'][0]['segments']) > 1:
                via_flag = True 
            if via_flag:
                dep_str = f"{dep['departure']['at'][:16]} → {o['itineraries'][0]['segments'][-1]['arrival']['at'][:16]}"
                ret_str = f"{ret['departure']['at'][:16]} → {o['itineraries'][1]['segments'][-1]['arrival']['at'][:16]}"
            else:
                dep_str = f"{dep['departure']['at'][:16]} → {dep['arrival']['at'][:16]}"
                ret_str = f"{ret['departure']['at'][:16]} → {ret['arrival']['at'][:16]}"
            
            # duration
            dur_dep = o['itineraries'][0]['duration'][2:].lower()
            dur_ret = o['itineraries'][1]['duration'][2:].lower()
            durations = f"{dur_dep} / {dur_ret}"
            
            # price
            total_price = o['price']['total']
            adult_price = next(t for t in o['travelerPricings'] if t['travelerType']=='ADULT')['price']['total']
            child_tp = next((t for t in o['travelerPricings'] if t['travelerType']=='CHILD'), None)
            child_price = child_tp['price']['total'] if child_tp else 0
            
            # cabin
            fb = next(t for t in o['travelerPricings'] if t['travelerType']=='ADULT')['fareDetailsBySegment'][0]
            icb = fb.get('includedCheckedBags', {})
            if 'weight' in icb:
                checked = f"{icb['weight']} {icb['weightUnit']}"
            else:
                checked = f"{icb.get('quantity', 0)} 개"
            cabin = fb.get('includedCabinBags', {}).get('quantity', 0)
            
            offers.append({
                'ID': offer_id,
                'Airlines (aricraft)': f"{carrier} ({aircraft})",
                'Transit': via_flag,
                'Departure schedule': dep_str,
                'Return schedule': ret_str,
                'Duration (one way/turnaround)': durations,
                'Total fare (USD)': total_price,
                'Adult': adult_price,
                'Child': child_price,
                'Checked': checked,
                'Cabin': cabin
            })
        return offers
    
    def search_fligiht(self, 
            originLocationCode: str, # IATA code
            destinationLocationCode: str, # IATA code
            departureDate: str, # ISO 8601
            returnDate: Optional[str] = None, # ISO 8601
            adults: Optional[int] = 1,
            children: Optional[int] = None,
            infants: Optional[int] = None,
            travelClass: Optional[str] = "ECONOMY", # ECONONY, PREMIUM_ECONOMY, BUSINESS, FIRST
            includedAirlineCodes: Optional[str] = None,
            excludedAirlineCodes: Optional[str] = None,
            nonStop: Optional[bool] = False,
            currencyCode: Optional[str] = "USD",# ISO 4217 format
            maxPrice: Optional[int] = None,
            max: Optional[int] = 5,
        ):
        """
        This tool to find flight. If children does not exist, children is null.

        Args:
            originLocationCode (str): city/airport IATA code from which the traveler will depart, e.g. BOS for Boston
            destinationLocationCode (str): city/airport IATA code to which the traveler is going, e.g. PAR for Paris
            departureDate (str): the date on which the traveler will depart from the origin to go to the destination. Dates are specified in the ISO 8601 YYYY-MM-DD format, e.g. 2017-12-25
            returnDate (str, optional): the date on which the traveler will depart from the destination to return to the origin. If this parameter is not specified, only one-way itineraries are found. If this parameter is specified, only round-trip itineraries are found. Dates are specified in the ISO 8601 YYYY-MM-DD format, e.g. 2018-02-28
            adults (int, optional): the number of adult travelers (age 12 or older on date of departure).
            children (int, optional): the number of child travelers (older than age 2 and younger than age 12 on date of departure) who will each have their own separate seat. If specified, this number should be greater than or equal to 0
            infants (int, optional): the number of infant travelers (whose age is less or equal to 2 on date of departure). Infants travel on the lap of an adult traveler, and thus the number of infants must not exceed the number of adults. If specified, this number should be greater than or equal to 0
            travelClass (str, optional): most of the flight time should be spent in a cabin of this quality or higher. The accepted travel class is economy, premium economy, business or first class. If no travel class is specified, the search considers any travel class(Available values : ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST)
            includedAirlineCodes (str, optional): This option ensures that the system will only consider these airlines. This can not be cumulated with parameter excludedAirlineCodes. (Airlines are specified as IATA airline codes and are comma-separated, e.g. 6X,7X,8X)
            excludedAirlineCodes (str, optional): This option ensures that the system will ignore these airlines. This can not be cumulated with parameter includedAirlineCodes. (Airlines are specified as IATA airline codes and are comma-separated, e.g. 6X,7X,8X)
            nonStop (bool, optional): if set to true, the search will find only flights going from the origin to the destination with no stop in between
            currencyCode (str, optional): if set to true, the search will find only flights going from the origin to the destination with no stop in between. defualt "USD"
            maxPrice (int, optional): maximum price per traveler. By default, no limit is applied. If specified, the value should be a positive number with no decimals
            max (int, optional): maximum number of flight offers to return. If specified, the value should be greater than or equal to 1. default 5

        Returns:
            str: The result of searching flight.

        """
        print('hello?')
        response = self.__request_api(self.url['airplan_by_schedule'], dict(locals()))
        result_json = {}
        try:
            json_parsed = json.loads(response.text)
            result_json = self.__search_parser(json_parsed)
            # result_json = json_parsed
        except BaseException as e:
            logger.error(f'Fail getting flgiht offer: {e}')
        return result_json
    
    def search_flight_by_origin(
        self,
        origin: str,
        departureDate: str | None = None,
        oneWay: bool | None = None,
        duration: str | None = None,
        nonStop: bool | None = None,
        maxPrice: int | None = None,
        viewBy: str | None = None,
    ):
        logger.info(f'in search_flight by origin inininiin')
        def flight_origin_parser(data:dict) -> str:
            target_columns = ['origin', 'destination', 'departureDate', 'returnDate', 'price']
            parsed_data = ','.join(target_columns)
            if data['data']:
                for dd in data['data']:
                    if dd['type'] == 'flight-destination':
                        parsed_data += '\n' + ','.join([dd[tc] if tc != 'price' else dd[tc]['total'] for tc in target_columns])
                parsed_data += f"\n currencies: {data['meta']['currency']}"
            return parsed_data
        logger.info(f'in search_flight by origin')
        response = self.__request_api(self.url['airplan_by_origin'], dict(locals()))
        logger.info(f'response: {response}, {response.text}')
        try: 
            json_parsed = json.loads(response.text)
            logger.info(f'result raw: {json_parsed}')
            csv_parsed = flight_origin_parser(json_parsed)
            logger.info(f'result: {csv_parsed}')
            return csv_parsed
        except BaseException as e:
            logger.error(f'Fail getting flight by origin: {e}')
        return None

    def list_hotel_by_city(
        self,
        cityCode: str, 
        radius: int | None = None,
        radiusUnit: str | None = None, # Unit of measurment
        chainCodes: list[str] | None = None, # hotel chain code
        amenities: list[str] | None = None, 
        ratings: list[str] | None = None,
        hotelSource: str | None = None,
    ) -> dict | None: # This information is almost last updated 2023
        """This tool to find hotels by city.

        Args:
            cityCode (str): Destination city code or airport code. In case of city code , the search will be done around the city center. Available codes can be found in IATA table codes (3 chars IATA Code). Example: PAR
            radius (int, optional): Maximum distance from the geographical coordinates express in defined units. The default unit is metric kilometer. Default value: 5
            radiusUnit (str, optional): Maximum distance from the geographical coordinates express in defined units. The default unit is metric kilometer. Available values: KM, MILE. default value: KM.
            chainCodes (list[str], optional): Array of hotel chain codes. Each code is a string consisted of 2 capital alphabetic characters.
            amenities (list[str], optional): List of amenities. Available values : SWIMMING_POOL, SPA, FITNESS_CENTER, AIR_CONDITIONING, RESTAURANT, PARKING, PETS_ALLOWED, AIRPORT_SHUTTLE, BUSINESS_CENTER, DISABLED_FACILITIES, WIFI, MEETING_ROOMS, NO_KID_ALLOWED, TENNIS, GOLF, KITCHEN, ANIMAL_WATCHING, BABY-SITTING, BEACH, CASINO, JACUZZI, SAUNA, SOLARIUM, MASSAGE, VALET_PARKING, BAR or LOUNGE, KIDS_WELCOME, NO_PORN_FILMS, MINIBAR, TELEVISION, WI-FI_IN_ROOM, ROOM_SERVICE, GUARDED_PARKG, SERV_SPEC_MENU
            ratings (list[str], optional): Hotel stars. Up to four values can be requested at the same time in a comma separated list. Available values: 1, 2, 3, 4, 5
            hotelSource (str, optional): Hotel source with values BEDBANK for aggregators, DIRECTCHAIN for GDS/Distribution and ALL for both. Available values : BEDBANK, DIRECTCHAIN, ALL. Default values: ALL.
        """
        response = self.__request_api(self.url['hotel_by_city'], dict(locals()))    
        try:
            json_parsed = json.loads(response.text)
            logger.info(f'hotels : {json_parsed}')
            return json_parsed
        except BaseException as e:
            logger.error(f'Fail getting hotel by city: {e}')
        return None

    def search_hotel_offer(
        self,
        hotelIds: str,
        adults: int | None = None,
        checkInDate: str | None = None,
        checkOutDate: str | None = None,
        contryOfResidence: str | None = None, 
        roomQuantity: int | None = None,
        priceRange: str | None = None,
        currency: str | None = None,
        paymentPolicy: str | None = None,
        boardType: str | None = None,
        includeClosed: bool | None = None,
        bestRateOnly: bool | None = None,
        lang: str | None =None,
    ) -> dict | None: # It has a lot of provider errors
        """This tool to find offer by hotelIds.

        Args:
            hotelIds (str): Amadeus property codes on 8 chars. Mandatory parameter for a search by predefined list of hotels.
            adults (int, optional): Number of adult guests (1-9) per room. Default value: 1.
            checkInDate (str, optional): Check-in date of the stay (hotel local date). Format YYYY-MM-DD. The lowest accepted value is the present date (no dates in the past). If not present, the default value will be today's date in the GMT time zone. Example: 2023-11-22
            checkOutDate (str, optional): Check-out date of the stay (hotel local date). Format YYYY-MM-DD. The lowest accepted value is checkInDate+1. If not present, it will default to checkInDate +1.
            countryOfResidence (str, optional): Code of the country of residence of the traveler expressed using ISO 3166-1 format.
            roomQuantity (int, optional): Number of rooms requested (1-9). Default value: 1.
            priceRange (str, optional): Filter hotel offers by price per night interval (ex: 200-300 or -300 or 100).
            currency (str, optional): Use this parameter to request a specific currency. ISO currency code (http://www.iso.org/iso/home/standards/currency_codes.htm).If a hotel does not support the requested currency, the prices for the hotel will be returned in the local currency of the hotel.
            paymentPolicy (str, optional): Filter the response based on a specific payment type. NONE means all types (default).
            boardType (str, optional): Filter response based on available meals: ROOM_ONLY = Room Only, BREAKFAST = Breakfast, HALF_BOARD = Diner & Breakfast(only for aggregators), FULL_BOARD = Full Board (only for Aggregators), ALL_INCLUSIVE = All Inclusive (only for Aggregators)
            includeClosed (bool, optional): Show all properties (include sold out) or available only. For sold out properties, please check availability on other dates.
            bestRateOnly (bool, optional): Used to return only the cheapest offer per hotel or all available offers.
            lang (str, optional): Requested language of descriptive texts. Examples: FR , fr , fr-FR.
        """
        response = self.__request_api(self.url['hotel_offers'], dict(locals()))
        try:
            json_parsed = json.loads(response.text)
            return json_parsed
        except BaseException as e:
            logger.error(f'Fail getting hotel by offer: {e}')
        return None
