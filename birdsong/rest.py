import requests, json
import urllib3

# For JSON payload packaging, import these for easier/auto serializing
from datetime import datetime, date
import arrow


VALIDATE_SSL_CERTS = False

class RestInterface(object):
    """Interface methods for talking to Canary."""
    apiVersion = 'api/v2'  #Chagned to v2

    __slots__ = ('host', 'https', 'ports', '_session', 'lastResults')
    
    def __init__(self, host='localhost', https=False, 
                 httpPort=80, httpsPort=443, verifySSL=VALIDATE_SSL_CERTS,
                 **configuration):        
        self.https = https
        self.host  = host
        self.ports = (httpPort, httpsPort)
        
        self._session = None

        self.lastResults = None

        self.verifySSL = verifySSL
        if not self.verifySSL:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        super().__init__(**configuration)

        
    @property
    def session(self):
        if not self._session:
            self._session = requests.Session()
        return self._session
    
    @classmethod
    def _coerceThingForJSON(cls, thing):
        """JSON serializes directly or not at all. 
        Dates are easy though.
        """
        if isinstance(thing, (datetime, date, arrow.Arrow)):
            return thing.isoformat()
        # Simply return it and hope the error gets to someone who can coerce it better
        return thing

    @classmethod
    def _packagePayload(cls, jsonData):
        return json.dumps(jsonData, default=cls._coerceThingForJSON)

    @staticmethod
    def _coerceToList(obj):
        """Ensure we're sending a list. 
        If it's just a thing, make that into a single entry list.
        """
        if not isinstance(obj,list):
            if isinstance(obj, (set,tuple)):
                obj = list(obj)
            else:
                obj = [obj]
        return obj
    
    # REST API methods
    
    def _post(self, apiUrl, jsonData):
        payload = self._packagePayload(jsonData)
        url = 'http%s://%s:%s/%s/%s' % ('s' if self.https else '', 
                                            self.host, 
                                            self.ports[self.https],
                                            self.apiVersion,
                                            apiUrl)
        response = self.session.post(url,data=payload, verify=(self.https and self.verifySSL))
        responseJson = response.json()
        self.lastResults = responseJson
       

    def _raiseUnhandledPostError(self, apiUrl, jsonData):
        """Separated out to allow subclasses to manage certain error states on their own"""
        if self.lastResults['errors']:
            if jsonData and 'password' in jsonData:
                jsonData['password'] = '********'
            raise RuntimeError('Canary API call to "%s" had errors: %r.\nData passed: %r' % (
                apiUrl, self.lastResults['errors'], jsonData))


    def _iterPost(self, apiUrl, jsonData, resultKey):
        self._post(apiUrl, jsonData)
        self._raiseUnhandledPostError(apiUrl, jsonData)
        while self.lastResults.get('continuation', False):
            results = self.lastResults[resultKey]
            if isinstance(results, (list,tuple)):
                for item in self.lastResults[resultKey]:
                    yield item
            else:
                yield results
            jsonData['continuation'] = self.lastResults['continuation']
            self._post(apiUrl, jsonData)
            self._raiseUnhandledPostError(apiUrl, jsonData)
        else:
            results = self.lastResults[resultKey]
            if isinstance(results, (list,tuple)):
                for item in self.lastResults[resultKey]:
                    yield item
            else:
                yield results
    
    def _singlePost(self, apiUrl, jsonData, resultKey):
        self._post(apiUrl, jsonData)
        self._raiseUnhandledPostError(apiUrl, jsonData)

        return self.lastResults[resultKey]
