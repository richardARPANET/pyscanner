from urllib import urlencode
import json
import time
import requests
import re

base_uri = 'www.skyscanner.net'
request_headers = {'User-Agent': 'PyScanner (https://github.com/richardasaurus/pyscanner)'}


class PyScanner:

    def __init__(self):
        pass

    def __build_url(self, path, params=None):
        default_params = {}

        if params:
            query_params = dict(default_params.items() + params.items())
            query_params = urlencode(query_params)
        else:
            query_params = urlencode(default_params)
        return 'http://{0}{1}?{2}'.format(base_uri, path, query_params)

    def __get_short_code(self, query):
        query = query.strip().lower()
        url = self.__build_url('/dataservices/geo/v1.0/autosuggest/uk/en/{0}'.format(query))
        r = requests.get(url, headers=request_headers).text
        places = json.loads(r)
        matched_p = None

        if len(places) > 1:
            for p in places:
                place_name = p['PlaceName'].lower()
                if place_name == query:
                    matched_p = p
                    break
        else:
            return None

        if matched_p is None and len(places) > 0:
            matched_p = places[0]

        if 'PlaceId' in matched_p:
            return matched_p['PlaceId']
        else:
            raise ValueError('No place id found in location')

    def __ymd_to_short(self, date):
        date = time.strptime(date, '%d/%m/%Y')
        short_date = str(date.tm_year)[2:] + str(date.tm_mon).zfill(2) + str(date.tm_mday).zfill(2)
        return short_date

    def __ymd_to_norm(self, date):
        date = time.strptime(date, '%d/%m/%Y')
        norm = '{0}-{1}-{2}'.format(str(date.tm_year), str(date.tm_mon).zfill(2), str(date.tm_mday).zfill(2))
        return norm

    def __parse_session_key(self, html):
        match = re.findall(r'"SessionKey":"([A-Za-z0-9_-]{36})","OriginPlace"', html, re.MULTILINE)
        if len(match) > 0:
            return match[0]
        else:
            raise ValueError('Could not find session key')

    def __parse_request_id(self, html):
        match = re.findall(r'"RequestId":"([A-Za-z0-9_-]{36})","WebsiteLogId"', html, re.MULTILINE)
        if len(match) > 0:
            return match[0]
        else:
            raise ValueError('Could not find request id')

    def __get_route_data(self, session_key):
        # sleep fixed http 204 error
        time.sleep(0.8)
        r_data_url = self.__build_url('/dataservices/routedate/v2.0/'+session_key)
        r = requests.get(r_data_url, headers=request_headers)
        json_resp = r.text
        try:
            return json.loads(json_resp, encoding='utf-8')
        except:
            raise ValueError('Could not load route data')

    def __get_sale_data(self, place_from, place_to, depart_date, return_date, request_id):
        url_string = '/dataservices/whosells/v1.0/UK/gbp/en/{0}/{1}/{2}/{3}?requestId={4}&src=alsoflies'
        url = self.__build_url(url_string.format(place_from,
                                                 place_to,
                                                 self.__ymd_to_norm(depart_date),
                                                 self.__ymd_to_norm(return_date),
                                                 request_id))
        r = requests.get(url, headers=request_headers).text
        try:
            return json.loads(r)
        except:
            raise ValueError('Could not load route data')

    def search(self, place_from, place_to, depart_date, return_date):
        place_from = self.__get_short_code(place_from)
        place_to = self.__get_short_code(place_to)
        depdate = self.__ymd_to_short(depart_date)
        retdate = self.__ymd_to_short(return_date)

        # get search results
        url = self.__build_url('/flights/{0}/{1}/{2}/{3}/x.html'.format(place_from, place_to, depdate, retdate))
        search_result_html = requests.get(url, headers=request_headers).text
        session_key = self.__parse_session_key(search_result_html)
        request_id = self.__parse_request_id(search_result_html)

        # get route data
        r_data = self.__get_route_data(session_key)

        quotes = r_data['Quotes']

        for q in quotes:
            q_id = q['QuoteRequestId']

            #add quote req data to quote
            for qr in r_data['QuoteRequests']:
                if qr['Id'] == q_id:
                    q['AgentId'] = qr['AgentId']

            #add agent data to quote
            for a in r_data['Agents']:
                if a['Id'] == q['AgentId']:
                    q['AgentName'] = a['Name']

        #get sale info
        whosells = self.__get_sale_data(place_from, place_to, depart_date, return_date, request_id)

        # final results list
        results = []

        for q in quotes:
            for agent in whosells['Agents']:
                #add agent name
                if q['AgentId'] == agent['AgentId']:
                    # add route link
                    if 'Routes' in agent:
                        q['Link'] = None
                        for route in agent['Routes']:
                            # if route matches our query, pick the link
                            if (
                                q['Link'] is None and
                                place_to == route['DestinationPlaceId'] and
                                place_from == route['OriginPlaceId']
                            ):
                                q['Link'] = 'http://{0}{1}'.format(base_uri, route['DeepLink'])
            # remove unwanted keys
            self.__dict_remove(['Id', 'AgentId', 'Age', 'IsReturn', 'QuoteRequestId', 'RequestDateTime'], q)
            # only add to results if link is present
            if q['Link'] is not None:
                results.append(q)

        #sort results by price, cheapest first
        results = sorted(results)
        results = sorted(results, key=lambda k: k['Price'])

        # dict to output class
        output = []
        for r in results:
            output.append(Result(**r))
        return output

    def __dict_remove(self, entries, the_dict):
        for key in entries:
            if key in the_dict:
                del the_dict[key]


class Result:
    def __init__(self, **kwargs):
        self.data = kwargs
        self.agent = self.data.get('AgentName')
        self.price = self.data.get('Price')
        self.link = self.data.get('Link')