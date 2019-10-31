from .rest import RestInterface


class UserTokenManagement(RestInterface):

    __slots__ = ('_username', '_password', '_userToken')
    
    def __init__(self, username='', password='', **configuration):
        
        self._username = username
        self._password = password
        self._userToken = None

        if self._username and self._password:
            configuration['https'] = True

        super().__init__(**configuration)
    

    @property
    def userToken(self):
        if not self._userToken:
            self._getUserToken()
        return self._userToken
     

    # User token API calls
    
    def _getUserToken(self):
        jsonData = {
            "username":self._username,
            "password":self._password,
            "application":"getData"
        }
        self._userToken = self._singlePost('getUserToken', jsonData, 'userToken')


    def _revokeUserToken(self):
        if self._userToken:
            self._post('revokeUserToken', {"userToken":self._userToken})
            self._userToken = None  
    

    # Context management
    
    def __enter__(self):
        self._getUserToken()
        return self
    
    def __exit__(self, *args):
        self._revokeUserToken()
        
    def __del__(self):
        self.__exit__()


    # Error Handling

    def _post(self, apiUrl, jsonData):

        super()._post(apiUrl, jsonData)

        # Check if it failed. If so, reload.
        if self.lastResults['statusCode'] == 'BadUserToken':
            assert 'userToken' in jsonData, "API '%s' called with bad user token without including one." % apiUrl
            self._userToken = None
            self._getUserToken()
            jsonData['userToken'] = self.userToken
            # Try again
            self._post(apiUrl, jsonData)


class LiveDataTokenManagement(UserTokenManagement, RestInterface):
    
    __slots__ = ('_liveDataTokens', '_liveDataConfigurations')

    def __init__(self, 
            liveTags=None,
            liveMode='AllValues',
            liveIncludeQuality=False,
            **configuration):
        super().__init__(**configuration)
        
        self._liveDataTokens = {}
        self._liveDataConfigurations = {}

        if liveTags:
            self._getLiveDataToken(liveTags, mode=liveMode, includeQuality=liveIncludeQuality)


    # Context management

    def __exit__(self, *args):
        self._revokeLiveDataToken()
        super().__exit__(*args)
    

    # Live data methods
    
    def _getLiveDataToken(self, tags, **configuration):
        if isinstance(tags, frozenset) and tags in self._liveDataTokens:
            return
        jsonData = {
            "userToken":self._userToken,
            "tags": self._coerceToList(tags)
        }
        jsonData.update(configuration)
        tagSet = frozenset(jsonData['tags'])
        if not tagSet in self._liveDataTokens:
            self._liveDataTokens[tagSet] = self._singlePost('getLiveDataToken', jsonData, 'liveDataToken')
            self._liveDataConfigurations[tagSet] = configuration.copy()


    def _revokeLiveDataToken(self, tags=None):
        if self._liveDataTokens:
            # If not specific, purge all tokens
            if not tags:
                for tagSet in frozenset(self._liveDataTokens):
                    self._revokeLiveDataToken(tagSet)
            else:
                tagSet = frozenset(tags)
                jsonData = {
                    "userToken":self._userToken,
                    "liveDataToken":self._liveDataTokens[tagSet],
                }
                self._post('revokeLiveDataToken', jsonData)
                del self._liveDataTokens[tagSet]
                del self._liveDataConfigurations[tagSet]

    

    def _revokeUserToken(self):
        self._revokeLiveDataToken()
        super()._revokeUserToken()


    def _rotateLiveDataToken(self, liveDataToken):
        """Rotate the live data token, maintaining the current configuration."""
        for tagSet,activeLiveDataToken in self._liveDataTokens.items():
            if liveDataToken == activeLiveDataToken:
                tagSetKey = tagSet 
                break
        else:
            raise KeyError("The liveDataToken could not be rotated because it was not cached.")

        configuration = self._liveDataConfigurations[tagSet]

        del self._liveDataTokens[tagSetKey]
        self._getLiveDataToken(tagSetKey, **configuration)

        return self._liveDataTokens[tagSetKey]


    # Error Handling

    def _post(self, apiUrl, jsonData):
        super()._post(apiUrl, jsonData)

        # Check if it failed. If so, reload.
        if self.lastResults['statusCode'] == 'BadLiveDataToken':
            assert 'liveDataToken' in jsonData, "API '%s' called with bad user token without including one." % apiUrl

            jsonData['liveDataToken'] = self._rotateLiveDataToken(jsonData['liveDataToken'])
            # Try again
            self._post(apiUrl, jsonData)


class SessionTokenManagement(UserTokenManagement, RestInterface):
    
    def __init__(self, historians=None, clientID="ClientID",
                 clientTimeout=60000,       # Timeout before Canary session closes
                 fileSize=32,               # MB for buffer file rollover
                 packetSize=1024000,        # Bytes per request
                 packetDelay=0,             # Useful for throttling
                 packetZip=False,           # Zip packets?
                 receiverPort=None,         # If the historian's reciever is different...
                 trackErrors=False,         # Op errors reported to /getErrors?
                 suppressInfoMessages=False,# Don't return Info as errors on /getErrors?
                 autoCreateDatasets=False,  # Create dataset if missing?
                 autoWriteNoData=True,      # "No Data" one tick after session closes?
                 extendData=True,           # Data extends w/active session but no updates?
                 insertReplaceData=False,   # Insert old data?
                 suppressTimestampErrors=False, # Don't return timestamp errors in /getErrors?
                 **configuration):

        self._sessionToken = None

        if not historians:
            self.historians = ['localhost']
            #raise ValueError("Must specify a historian to target for sender service.")
        elif isinstance(historians, list):
            self.historians = historians
        elif isinstance(historians, str):
            self.historians = historians.split(',')
        else:
            self.historians = [historians]

        self.clientID = clientID

        self._settings = {
            'clientTimeout': clientTimeout,
            'fileSize': fileSize,
            'packetSize': packetSize,
            'packetDelay': packetDelay,
            'packetZip': packetZip,
            'receiverPort': receiverPort,
            'trackErrors': trackErrors,
            'suppressInfoMessages': suppressInfoMessages,
            'autoCreateDatasets': autoCreateDatasets,
            'autoWriteNoData': autoWriteNoData,
            'extendData': extendData,
            'insertReplaceData': insertReplaceData,
            'suppressTimestampErrors': suppressTimestampErrors,            
        }
        
        super().__init__(**configuration)

 
    # Context management

    def __enter__(self):
        super().__enter__()
        self._getSessionToken()
        return self


    def __exit__(self, *args):
        self._revokeSessionToken()
        super().__exit__(*args)


    # Session token API calls

    @property
    def sessionToken(self):
        if not self._sessionToken:
            self._getSessionToken()
        return self._sessionToken
    
    
    def _getSessionToken(self):
        jsonData = {
            "userToken":self.userToken,
            "historians":self.historians,
            "clientID":self.clientID,
            "settings": self._settings,
        }
        self._sessionToken = self._singlePost('getSessionToken', jsonData, 'sessionToken')


    def _revokeSessionToken(self):
        if self._sessionToken:
            assert self._userToken, "Session token without user token!"
            jsonData = {
                "userToken":self._userToken,
                "sessionToken":self._sessionToken
            }
            self._post('revokeSessionToken', jsonData)
            self._sessionToken = None


    # Session management

    def getErrors(self):
        assert self._sessionToken, "Session token missing - can't get errors of missing session."
        jsonData = {
            "userToken":self._userToken,
            "sessionToken":self._sessionToken
        }
        self._singlePost('getErrors', jsonData)        


    def keepAlive():
        jsonData = {
            "userToken":self.userToken,
            "sessionToken":self.sessionToken
        }
        self._post('keepAlive', jsonData)


    def updateSettings(self, **settings):
        """Modify the active session settings. See the class init
        arguments for options.

        Args:
            settings: (dict) sessiont properties to set.
        """
        jsonData = {
            "userToken": self.userToken,
            "sessionToken": self.sessionToken,
            "settings": settings
        }
        self._post("updateSettings", jsonData)
        if self.lastResults['statusCode'] == "Good":
            self._settings = settings


    # Error Handling

    def _post(self, apiUrl, jsonData):

        super()._post(apiUrl, jsonData)

        # Check if it failed. If so, reload.
        if (   self.lastResults['statusCode'] == 'BadSessionToken' 
            or (    self.lastResults['statusCode'] == 'Error' 
                and 'Session token is invalid or has expired' in self.lastResults['errors'])):
            assert 'sessionToken' in jsonData, "API '%s' called with bad session token without including one." % apiUrl
            self._sessionToken = None
            self._getSessionToken()
            jsonData['sessionToken'] = self.sessionToken
            # Try again
            self._post(apiUrl, jsonData)


