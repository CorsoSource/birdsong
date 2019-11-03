"""
	A Python interface to the Canary REST API

"""

name = 'birdsong'


__all__ = ['CanaryView', 'CanarySender', 'Tvq', 'Property', 'Annotation']



###########################################################
#     IMPORTS
###########################################################


# Ensure that the library loads the Ignition API stuff
import system
from collections import defaultdict


# Internally, all timestamps will be held as the OffsetDateTime objects.
# It maintains precision, can be manipulated, and writes back as ISO8601.
# TL;DR: OffsetDateTime is the least worst solution that doesn't involve
#        dragging in an external library.
# Instant is included because 
from java.time import OffsetDateTime, Instant, ZoneId
from java.time.format import DateTimeFormatter
from java.text import SimpleDateFormat
from java.util import Date



###########################################################
#     SETTINGS
###########################################################


VALIDATE_SSL_CERTS = False

DEFAULT_SENDER_PORT_ANONYMOUS_HTTP = '55253'
DEFAULT_SENDER_PORT_USERNAME_HTTPS = '55254'      

DEFAULT_VIEW_PORT_ANONYMOUS_HTTP = '55235'
DEFAULT_VIEW_PORT_USERNAME_HTTPS = '55236'



###########################################################
#     HELPER FUNCTIONS
###########################################################


def chunks(l, n):
    """Yield successive n-sized chunks from l.
    From https://stackoverflow.com/a/312464/11902188
    """
    for i in range(0, len(l), n):
        yield l[i:i + n]



###########################################################
#     VALUES HELPER CLASSES
###########################################################


class BaseValue(object):

    __slots__ = ('_tuple')

    _fields = ('value',)
    _optional = (True,)

    _timeFormat = None

    def __init__(self, value=None):
        self._tuple = (value,)
    
    @classmethod
    def keys(cls):
        return cls._fields

    def values(self, iso8601=False):
        return self._astuple(iso8601)

    def _astuple(self, iso8601=False):
        if iso8601:
            return tuple(value.toString() 
                         if isinstance(value, (OffsetDateTime,Instant)) 
                            else value # assume the best?
                         for value,optional 
                         in zip(self._tuple, self._optional) 
                         if not optional or not (value is None))
        else:
            return tuple(value 
                         for value,optional 
                         in zip(self._tuple, self._optional) 
                         if not optional or not (value is None))

    def _asdict(self,iso8601=False):
        return dict(zip(self._fields, self._astuple(iso8601)))

    def __getitem__(self, key):
        try:
            return self._tuple[key]
        except(TypeError, IndexError):
            return self._tuple[self._ixLookup[key]]

    def __iter__(self):
        return iter(self._astuple())

    def __repr__(self):
        return repr(self._asdict(iso8601=True))

    # Some time helper / coersion bits.
    def setTimeFormat(self, format):
        """In case timestamps are in a crazy format, enter a custom formatter here.
        Don't try to need this: just use ISO8601 for your date format like Canary does:
        YYYY-MM-DD HH:mm:ss.SSSSSSZ
        """
        if isinstance(format, (str, unicode)):
            self._timeFormat = DateTimeFormatter.ofPattern(format)
        elif isinstance(format, DateTimeFormatter):
            self._timeFormat = format
        elif isinstance(format, SimpleDateFormat):
            self._timeFormat = format
            #raise NotImplementedError('The SimpleDateFormat parser can lose precision on conversion. Use the improved Java 8+ time libraries via java.time.format.DateTimeFormatter')
        else:
            raise NotImplementedError('The given format "%r" is not implemented for birdsong yet.' % format)

    def _coerceTimestamp(self, timestamp):
        if isinstance(timestamp, str):
            # A timestamp on Christ's Epoch should be understood as an error.
            # It's not a real time, so return None. It's essentially a soft error.
            if timestamp.startswith('0001-01-01'):
                return None

            if self._timeFormat:
                if isinstance(self._timeFormat, DateTimeFormatter):
                    return OffsetDateTime.parse(timestamp, self._timeFormat)
                elif isinstance(self._timeFormat, SimpleDateFormat):
                    return self._coerceTimestamp(self._timeFormat.parse(timestamp))
                else:
                    raise NotImplementedError('The formatter "%r" is not yet usable automatically for the birdsong helper classes' % self._timeformat)

            # For convenience and ease of use, we'll just double check that the T is in the right place for the parser
            timestamp = timestamp.replace(' ', 'T')

            try: # the iso8601 format first
                return OffsetDateTime.parse(timestamp)
            except ValueError:
                raise ValueError('%r attempted to parse "%s" without a time format' % (self, timestamp))
        
        # Assume the date object was created locally. Because.
        elif isinstance(timestamp, Date):
            return OffsetDateTime.ofInstant(timestamp.toInstant(), ZoneId.systemDefault())
        
        # Assume the Instant is in UCT, because it's supposed to be.
        elif isinstance(timestamp, Instant):
            return OffsetDateTime.ofInstant(timestamp, ZoneId.of('UTC'))
        
        # Trivial case
        elif timestamp is None:
            return None
        else:
            raise NotImplementedError('Birdsong on Java does not yet automatically consume this date format: %r' % timestamp)
        


def _finalize(BVClass, aliases=None):
    setattr(BVClass, '_ixLookup', dict((field,ix) 
                                       for ix,field 
                                       in enumerate(BVClass._fields) ) )
    for ix,key in enumerate(BVClass._fields):
        setattr(BVClass, key, property(lambda self, ix=ix: self._tuple[ix]))
        setattr(BVClass, 'get%s' % key.capitalize(), lambda self, ix=ix: self._tuple[ix])
    if aliases:
        for ix,key in enumerate(aliases):
            setattr(BVClass, key, property(lambda self, ix=ix: self._tuple[ix]))


class Tvq(BaseValue):
    _fields = ('timestamp', 'value', 'quality')
    _optional = (False, False, True)

    def __init__(self, timestamp, value, quality=None):
        timestamp = self._coerceTimestamp(timestamp)

        self._tuple = (timestamp, value, quality)
    
_finalize(Tvq, 't v q'.split())


class Property(BaseValue):
    _fields = ('name', 'timestamp', 'value', 'quality')
    _optional = (False, False, False, True)

    def __init__(self, name, timestamp, value, quality=None):
        timestamp = self._coerceTimestamp(timestamp)

        self._tuple = (name, timestamp, value, quality)

_finalize(Property, 'n t v q'.split())


class Annotation(BaseValue):
    _fields = ('user', 'timestamp', 'value', 'createdAt')
    _optional = (False, False, False, True)

    def __init__(self, user, timestamp, value, createdAt=None):
        timestamp = self._coerceTimestamp(timestamp)
        if createdAt:
            createdAt = self._coerceTimestamp(createdAt)
        self._tuple = (user, timestamp, value, createdAt)

_finalize(Annotation, 'u t v c'.split())
    

VALUE_TYPE_MAP = {'tvq': Tvq, 'property': Property, 'annotation': Annotation}
   
def createValue(valueType='tvq', *values):
    return VALUE_TYPE_MAP[valueType.lower()](*values)



###########################################################
#     REST INTERFACE
###########################################################


class RestInterface(object):
    """Interface methods for talking to Canary."""
    apiVersion = 'api/v1'

    __slots__ = ('host', 'https', 'ports', 'lastResults')
    
    def __init__(self, host='localhost', https=False, 
                 httpPort=80, httpsPort=443, verifySSL=VALIDATE_SSL_CERTS,
                 **configuration):        
        self.https = https
        self.host  = host
        self.ports = (httpPort, httpsPort)
        
        self.lastResults = None

        self.verifySSL = verifySSL

        super(RestInterface,self).__init__(**configuration)

    
    @staticmethod
    def _packagePayload(jsonData):
        return system.util.jsonEncode(jsonData, 2)

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
                                            
        response = system.net.httpPost(url, contentType='applicatfion/json', postData=jsonData, 
                                       bypassCertValidation=not (self.https and self.verifySSL))
        responseJson = system.util.jsonDecode(response)
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



###########################################################
#     TOKEN MANAGEMENT
###########################################################


class UserTokenManagement(RestInterface):

    __slots__ = ('_username', '_password', '_userToken')
    
    def __init__(self, username='', password='', **configuration):
        
        self._username = username
        self._password = password
        self._userToken = None

        if self._username and self._password:
            configuration['https'] = True

        super(UserTokenManagement, self).__init__(**configuration)
    

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

        super(UserTokenManagement, self)._post(apiUrl, jsonData)

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
        super(LiveDataTokenManagement,self).__init__(**configuration)
        
        self._liveDataTokens = {}
        self._liveDataConfigurations = {}

        if liveTags:
            self._getLiveDataToken(liveTags, mode=liveMode, includeQuality=liveIncludeQuality)


    # Context management

    def __exit__(self, *args):
        self._revokeLiveDataToken()
        super(LiveDataTokenManagement,self).__exit__(*args)
    

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
        super(LiveDataTokenManagement,self)._revokeUserToken()


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
        super(LiveDataTokenManagement, self)._post(apiUrl, jsonData)

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
        
        super(SessionTokenManagement,self).__init__(**configuration)

 
    # Context management

    def __enter__(self):
        super(SessionTokenManagement,self).__enter__()
        self._getSessionToken()
        return self


    def __exit__(self, *args):
        self._revokeSessionToken()
        super(SessionTokenManagement,self).__exit__(*args)


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

        super(SessionTokenManagement, self)._post(apiUrl, jsonData)

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



###########################################################
#     CANARY VIEW
###########################################################


class CanaryView(LiveDataTokenManagement, UserTokenManagement):
    
    apiVersion = 'api/v1'
    
    def __init__(self,
                 httpPort =DEFAULT_VIEW_PORT_ANONYMOUS_HTTP,
                 httpsPort=DEFAULT_VIEW_PORT_USERNAME_HTTPS,
                 **configuration):
        super(CanaryView, self).__init__(httpPort =httpPort, httpsPort=httpsPort, **configuration)

                 
    # Browse Methods
    
    def browseNodes(self, path=''):
        """Get the child folders in the given path.

        Args:
            path: (str) Path the search under

        Returns:
            List of folders in the path.
        """
        jsonData = {
            "userToken":self.userToken,
            "path":path
        }
        return self._singlePost("browseNodes", jsonData, 'nodes')

    def browseTags(self,path='', search='', deep=False):
        """Get a list of the tags for the given path/search.

        Args:
            path: (str) Path to seach under
            search: (str) String pattern that tag paths must contain
            deep: (bool) Recursively search into all paths

        Returns:
            Generator of tag paths
        """
        jsonData = {
            "userToken":self.userToken,
            "path":path,
            "deep": deep,
            "search": search
        }
        return self._iterPost("browseTags", jsonData, "tags")
    
    def browseStatus(self, views):
        """Look up the status sequence of the given view(s)

        Args:
            views: (str, list of str) Canary views to check up on

        Returns:
            Sequence number for view, or an iterable of views and their sequences if list provided
        """           
        jsonData = {
            "userToken":self.userToken,
            'views': self._coerceToList(views)
        }
        statuses = self._singlePost('browseStatus', jsonData, 'views')

        if isinstance(views, (str,unicode)):
            return statuses.get(views,{}).get('sequence', None)
        else:
            return ((viewName,statuses.get(viewName,{}).get('sequence',None)) 
                    for viewName in views)
    
    # Data methods
    
    def getAggregates(self):
        """Get the list of aggregates the Canary engine can calculate.

        Returns:
            Dict of aggregates function names and their explanations.
        """
        jsonData = {
            'userToken': self.userToken
        }
        return self._singlePost('getAggregates', jsonData, 'aggregates')
    
    def getQualities(self, qualities):
        """Converts the given integer quality(s) to human readable strings.
        
        Args:
            qualities: (int, list of ints) quality codes to explain

        Returns:
            Dict of quality codes and their meaning
        """                
        jsonData = {
            'userToken': self.userToken,
            'qualities': self._coerceToList(qualities)
        }    
        return self._singlePost('getQualities', jsonData, 'qualities')
    
    def getTagProperties(self, tags):
        """Returns the properties for the given tag(s), if any.

        Args:
            tags: (str, list of str) Tags to get properties for

        Returns:
            - Generator yielding properties for a tag or tag paths and their property dicts
        """
        jsonData = {
            'userToken': self.userToken,
            'tags': self._coerceToList(tags)
        }    
        tagPropDict = self._singlePost('getTagProperties', jsonData, 'properties')
    
        # Return the dict directly if just a single tag was asked for
        if isinstance(tags, (str,unicode)):
            return tagPropDict.get(tags, {})
        # ... otherwise return an iterator
        else:
            return ((tagPath, tagPropDict.get(tagPath, {})) for tagPath in tags)


    def _getTagData(self, tags, **constraints):
        jsonData = {
            'userToken': self.userToken,
            'tags': self._coerceToList(tags)
        }
        jsonData.update(constraints)
        return self._iterPost('getTagData', jsonData, 'data')


    def getTagData(self, tags, **constraints):
        """Returns the data for the given tags.
          If just a tag path is given, results are the values only.
          If a list is given, an iterable of tagpaths and their values is returned.
            (For example, you can use this in a for loop like
               for tagpath,values in view.getTagData(taglist) )


        Constraints defines the range and type of data returned:
            startTime: (str) Earliest time; tradtional or relative date/times
            endTime: (str) Latest time; traditional or relative date/times
            aggregateName: (str) Function to apply to data (call getAggregates for available options)
            aggregateInterval: (str) Interval to apply for function; traditional or relative time spans
            includeQuality: (bool: false) Include the value's quality code
            maxSize: (int:10000) Maximum number of values to return

        Args:
            tags: (str,list) Tag path or list of tag paths to pull data for

        Returns:
            - Iterator yielding values for a tag path or dict of tags and their qualified values
        """
        # User friendly conversion (at least because I do this constantly...)
        userFriendlyAutoConversions = [
            ('startDate', 'startTime'),
            ('start', 'startTime'),

            ('endDate', 'endTime'),
            ('end', 'endTime'),
        ]
        for fromKey,toKey in userFriendlyAutoConversions:
            if fromKey in constraints:
                constraints[toKey] = constraints[fromKey]
                del constraints[fromKey]

        # If only a single tag path was provided, simply return values
        if isinstance(tags, (str, unicode)):
            tagPath = tags 
            for valueChunk in self._getTagData(tagPath, **constraints):
                # If only one value is returned, the result is NOT a list of one element
                if valueChunk.get(tagPath,[]) and not isinstance(valueChunk[tagPath][0], list):
                    return [Tvq(*valueChunk[tagPath])]
                else:
                    return [Tvq(*value) for value in valueChunk.get(tagPath,[])]
        else:
            tagData = {tagPath:[] for tagPath in tags}
            for tagChunk in self._getTagData(tags, **constraints):
                for tagPath,values in tagChunk.items():
                    # Compensate for non-list-wrapped values
                    if values and not isinstance(values[0], list):
                        tagData[tagPath].append(Tvq(*values))
                    else:
                        tagData[tagPath].extend([Tvq(*value) for value in values])

            return ((tagPath, tagData.get(tagPath, [])) for tagPath in tags)


    def getLiveData(self, tags=None, **configuration):
        """Returns the live data for the given tag(s). Each subsequent call returns new data.
          If just a tag path is given, results are the values only.
          If a list is given, an iterable of tagpaths and their values is returned.
            (For example, you can use this in a for loop like
               for tagpath,values in view.getLiveData(taglist) )
        
        The configuration keys are ignored after the live data connection is set up.
          Directly revoke the live data token manually to reconfigure again.
          (This is because reconfiguring the connection for a tag will result in the old
           connection being lost, losing context and making this difficult to manage.)
        """
        # Once live data is initialized, continue pulling
        # But only allow this if it's in use once
        #   (this is to allow for convenient context manager work)
        if not tags:
            if not len(self._liveDataTokens) == 1:
                raise ValueError("getLiveData() called without a tag list _and_ did not have only one live data token.")
            liveDataToken = list(self._liveDataTokens.values())[0]
        else:
            justThatTagMaam = isinstance(tags, (str, unicode))
                
            tags = self._coerceToList(tags)
            tagSet = frozenset(tags)
            if not tagSet in self._liveDataTokens:
                self._getLiveDataToken(tags, **configuration)
            liveDataToken = self._liveDataTokens[tagSet]
            
        jsonData = {
            "userToken":self._userToken,
            "liveDataToken":self._liveDataTokens[tagSet],
        }
        if justThatTagMaam:
            tagPath = tags[0]
            for page in self._iterPost('getLiveData', jsonData, 'data'):
                if not tagPath in page:
                    continue
                for value in page[tagPath]:
                    yield Tvq(*value)
        else:
            for page in self._iterPost('getLiveData', jsonData, 'data'):
                for tagPath,values in page.items():
                    yield tagPath, [Tvq(*value) for value in values]



    # Error Handling

    def _post(self, apiUrl, jsonData):
        super(CanaryView, self)._post(apiUrl, jsonData)

        # Check if it failed. If so, reload.
        if self.lastResults['statusCode'] == 'BadLicense':
            raise RuntimeError("The target Canary instance is not licensed for third party View usage.")



###########################################################
#     CANARY SENDER
###########################################################


class CanarySender(SessionTokenManagement, UserTokenManagement):
    
    __slots__ = ('_lastStoredTags')

    def __init__(self, 
                 httpPort =DEFAULT_SENDER_PORT_ANONYMOUS_HTTP, 
                 httpsPort=DEFAULT_SENDER_PORT_USERNAME_HTTPS, 
                 **configuration):
        """Canary Sender interface for pushing data to the historian service(s).

        Use with a context manager for automatic token management.
        For example, to talk to the default localhost historian using anonymous access:

            with CanarySender() as send:
                send.storeData(tvqs)

        Args:
            httpPort: (str) Port configured for anonymous HTTP access
            httpsPort: (str) Port configured for user/pass HTTPS access
        """
        super(CanarySender, self).__init__(httpPort =httpPort, httpsPort=httpsPort, **configuration)


    # Storage - File options

    def createNewFile(self, dataset, timestamp):
        """Create a new file for the selected dataset, marked at the given timestamp.
        Like fileRollover, but the tags for the file will only show those in 
          this particular file.

        Args:
            dataset: (str) Name of the dataset
            timestamp: (str) Datetime label for new file
        """
        jsonData = {
            "userToken":self.userToken,
            "sessionToken":self.sessionToken, 
            "dataset":dataset,
            "fileTime":timestamp
        }
        self._post('createNewFile', jsonData)

        
    def fileRollover(self, dataset, timestamp):
        """Create a new rolled over file labeled at the given timestamp.
        Like createNewFile, but ensures that previous file's tags are
          available, even if no data has been inserted for this file.

        Args:
            dataset: (str) Name of the dataset
            timestamp: (str) Datetime label for new file
        """
        jsonData = {
            "userToken":self.userToken,
            "sessionToken":self.sessionToken, 
            "dataset":dataset,
            "fileTime":timestamp
        }
        self._post('fileRollOver', jsonData)
    

    # Storage - Configuration

    def configureTags(self, tags):
        """Initialize parameters on the given tags.
        Each entry in the tags dict is a dict of either/both of 
            transform: (str) calculation to apply on incoming data before storing
            normalize: (str) time span to snap incoming values to.

        Args:
            tags: (dict) tags and their dict of properties and values
        """
        jsonData = {
            "userToken": self.userToken,
            "sessionToken": self.sessionToken,
            "tags": tags 
        }
        self._post("configureTags", jsonData)



    # Storage - Data
    
    def storeData(self, tvqs={}, properties={}, annotations={}, maxPageSize=25000):
        """Store data in the historian.
        Three types of data may be inserted, values, tag properties, and annotations.
        Each entry is a dictionary of tag path keys and arrays of arrays values.
        The value tuples/lists for each is:
            tvqs: (timestamp, value, quality (opt))
            properties: (prop name, timestamp, value, quality (opt)) 
            annotations: (user, timestamp, value, createdAt (opt))

        The maxPageSize limits the size of very large payloads to Canary. If the
          number of values for each tag in each dict totals more than this, then
          the update will be broken up into smaller chunks of maxPageSize each.

        Args:
            tvqs: (dict of lists) Values for tags
            properties: (dict of lists) Properties for tags
            annotations: (dict of lists) Annotations for tags
            maxPageSize: (int) Number of values to send in a single update payload        """
        
        # Make sure that we send a proper list of lists.
        def coerceList(someList):
            allowedTypes = (Tvq, Property, Annotation)
            # If the list isn't empty, check if it's a singleton entry
            if someList and not isinstance(someList[0], (tuple, list) + allowedTypes):
                return [someList.values(iso8601=True) 
                            if isinstance(someList, allowedTypes) 
                            else someList
                        ]
            else:
                return [value.values(iso8601=True) 
                            if isinstance(value, allowedTypes) 
                            else value
                        for value in values
                        ]

        # Convert from helpers objects, if needed. (This ensures it serializes correctly)
        for tag,values in tvqs.items():
            tvqs[tag] = coerceList(values)

        for tag,values in properties.items():
            properties[tag] = coerceList(values)

        for tag,values in annotations.items():
            annotations[tag] = coerceList(values)

        dataToSend = {
            'tvqs': tvqs,
            'properties': properties,
            'annotations': annotations
        }

        if sum(sum(len(values) for values in tagDict.values())
               for tagDict in dataToSend.values()
               ) < maxPageSize:
            self._storeData(**dataToSend)
        else:
            # Page out the data. Sort to make ensure earliest entries are added first
            pageLen = 0
            pageDict = {}

            for entryType in ('tvqs', 'properties', 'annotations'):
                pageDict[entryType] = tagDict = {}

                for tag,values in dataToSend[entryType].items():
                    tagDict[tag] = []

                    for value in values:
                        tagDict[tag].append(value)
                        pageLen += 1

                        if pageLen >= maxPageSize:
                            self._storeData(**pageDict)

                            # reset the page counters
                            pageDict[entryType] = tagDict = {}
                            tagDict[tag] = []
                            pageLen = 0
            else:
                if pageLen:
                    self._storeData(**pageDict)

        self._lastStoredTags = set(tvqs.keys()) | set(properties.keys()) | set(annotations.keys())


    def _storeData(self, tvqs={}, properties={}, annotations={}):
        """The call that executes storeData."""
        dataEntry = {
            "userToken":self.userToken,
            "sessionToken":self.sessionToken, 
        }
        if any((tvqs, properties, annotations)):
            if tvqs:
                dataEntry['tvqs'] = tvqs
            if properties:
                dataEntry['properties'] = properties
            if annotations:
                dataEntry['annotations'] = annotations
            self._post('storeData', dataEntry)


    def noData(self, tags=[]):
        """Adds a "No Data" entry to the end of the tags provided.
        Useful for braketting and marking a separtion chunks of tag data.

        Args:
            tags: (list) Tag paths to append to
        """
        if not tags:
            assert self._lastStoredTags, "Can't set 'No Data' without context. No tags given and _lastStoredTags is empty."
            tags = self._lastStoredTags

        dataEntry = {
            "userToken":self.userToken,
            "sessionToken":self.sessionToken,
            "tags": self._coerceToList(tags)
        }
        self._post('noData', dataEntry)


    # Info services

    def version(self):
        """Get the version of the sender service.

        Returns:
            - (str) version label 
        """
        jsonData = {
            "userToken": self.userToken
        }
        return self._singlePost("version", jsonData, "version")

    def compatibleVersion(self):
        """Get the compatible version of the sender service.
        
        Returns:
            - (str) API version sender service is compatible with
        """
        jsonData = {
            "userToken": self.userToken
        }
        return self._singlePost("compatibleVersion", jsonData, "compatibleVersion")

    def getDatasets(self, historian):
        """Get the datasets in a historian.

        Args:
            historian: (str) historian to list datasets for

        Returns:
            - (list) dataset names in historian
        """
        jsonData = {
            "userToken": self.userToken,
            "historian": historian
        }
        return self._singlePost("getDatasets", jsonData, "datasets")