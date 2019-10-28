import requests, json
import urllib3

VALIDATE_SSL_CERTS = False

class RestInterface(object):
    """Interface methods for talking to Canary."""
    apiVersion = 'api/v1'

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
    
    @staticmethod
    def _packagePayload(jsonData):
        return json.dumps(jsonData)

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
        jsonData = self._packagePayload(jsonData)

        url = 'http%s://%s:%s/%s/%s' % ('s' if self.https else '', 
                                            self.host, 
                                            self.ports[self.https],
                                            self.apiVersion,
                                            apiUrl)
        response = self.session.post(url,data=jsonData, verify=(self.https and self.verifySSL))
        responseJson = response.json()
        self.lastResults = responseJson
        
    def _iterPost(self, apiUrl, jsonData, resultKey):
        self._post(apiUrl, jsonData)
        while self.lastResults.get('continuation', False):
            results = self.lastResults[resultKey]
            if isinstance(results, (list,tuple)):
                for item in self.lastResults[resultKey]:
                    yield item
            else:
                yield results
            jsonData['continuation'] = self.lastResults['continuation']
            self._post(apiUrl, jsonData)
        else:
            results = self.lastResults[resultKey]
            if isinstance(results, (list,tuple)):
                for item in self.lastResults[resultKey]:
                    yield item
            else:
                yield results
    
    def _singlePost(self, apiUrl, jsonData, resultKey):
        self._post(apiUrl, jsonData)
        if self.lastResults['errors']:
            raise RuntimeError('Canary API call to "%s" had errors: %r.\nData passed: %r' % (
                apiUrl, self.lastResults['errors'], jsonData))
        return self.lastResults[resultKey]
