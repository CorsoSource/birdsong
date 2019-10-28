from .tokens import UserTokenManagement, SessionTokenManagement
from .values import Tvq, Property, Annotation
from collections import defaultdict


DEFAULT_SENDER_PORT_ANONYMOUS_HTTP = '55253'
DEFAULT_SENDER_PORT_USERNAME_HTTPS = '55254'      


def chunks(l, n):
    """Yield successive n-sized chunks from l.
    From https://stackoverflow.com/a/312464/11902188
    """
    for i in range(0, len(l), n):
        yield l[i:i + n]


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
                return [someList]
            else:
                return [value.values() if isinstance(value, allowedTypes) else value
                        for value in values]

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
               for tagDict in dataToSend.values()) < maxPageSize:
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