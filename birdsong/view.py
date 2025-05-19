from .tokens import UserTokenManagement, LiveDataTokenManagement
from .values import Tvq


DEFAULT_VIEW_PORT_ANONYMOUS_HTTP = '55235'
DEFAULT_VIEW_PORT_USERNAME_HTTPS = '55236'


class CanaryView(LiveDataTokenManagement, UserTokenManagement):
    
    apiVersion = 'api/v2'
    
    def __init__(self,
                 httpPort =DEFAULT_VIEW_PORT_ANONYMOUS_HTTP,
                 httpsPort=DEFAULT_VIEW_PORT_USERNAME_HTTPS,
                 **configuration):
        super().__init__(httpPort =httpPort, httpsPort=httpsPort, **configuration)

                 
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

        if isinstance(views, str):
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
        if isinstance(tags, str):
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
            includeBounds: (bool: false) Include bounding values for Raw Data calls
            useTimeExtension: (bool: true) Retrieve time extended timestamp for last value calls
            quality: (str) Quality of data to return for last value calls ('any', 'good', 'non-bad')
            maxSize: (int:10000) Maximum number of values to return

        Args:
            tags: (str,list) Tag path or list of tag paths to pull data for

        Returns:
            - Iterator yielding values for a tag path or dict of tags and their qualified values
        """
       # Add timezone handling if not already set via userToken
        if 'timezone' not in constraints and not self._username:
            constraints['timezone'] = 'UTC'  # Default to UTC if not specified

        # Handle new parameters
        if 'useTimeExtension' not in constraints:
            constraints['useTimeExtension'] = True  # Defaults to true in v2

        # If quality is specified and not 'any', force useTimeExtension to false
        if 'quality' in constraints and constraints['quality'] != 'any':
            constraints['useTimeExtension'] = False

        # User friendly conversion
        userFriendlyAutoConversions = [
            ('startDate', 'startTime'),
            ('start', 'startTime'),
            ('endDate', 'endTime'),
            ('end', 'endTime'),
        ]
        for fromKey, toKey in userFriendlyAutoConversions:
            if fromKey in constraints:
                constraints[toKey] = constraints[fromKey]
                del constraints[fromKey]

        # If only a single tag path was provided, simply return values
        if isinstance(tags, str):
            tagPath = tags
            try:
                values = []
                for valueChunk in self._getTagData([tagPath], **constraints):
                    # Add debug output
                    print(f"Debug - valueChunk: {valueChunk}")

                    # Handle the new response format where each value is an object with t and v properties
                    if tagPath in valueChunk:
                        for item in valueChunk[tagPath]:
                            if isinstance(item, dict) and 't' in item and 'v' in item:
                                # Extract time and value from the object
                                t = item['t']
                                v = item['v']
                                # Quality might be included or might be None/missing
                                q = item.get('q', None)
                                values.append(Tvq(t, v, q))
                return values
            except Exception as e:
                print(f"Error in getTagData: {str(e)}")
                return []
        else:
            tagData = {tagPath: [] for tagPath in tags}
            try:
                for tagChunk in self._getTagData(tags, **constraints):
                    # Add debug output
                    print(f"Debug - tagChunk: {tagChunk}")

                    for tagPath in tags:
                        if tagPath in tagChunk:
                            for item in tagChunk[tagPath]:
                                if isinstance(item, dict) and 't' in item and 'v' in item:
                                    # Extract time and value from the object
                                    t = item['t']
                                    v = item['v']
                                    # Quality might be included or might be None/missing
                                    q = item.get('q', None)
                                    tagData[tagPath].append(Tvq(t, v, q))

                return ((tagPath, tagData.get(tagPath, [])) for tagPath in tags)
            except Exception as e:
                print(f"Error in getTagData: {str(e)}")
                return ((tagPath, []) for tagPath in tags)
        
    def _getTagData2(self, tags, **constraints):
        jsonData = {
            'userToken': self.userToken,
            'tags': self._coerceToList(tags)    
        }
        jsonData.update(constraints)
        return self._iterPost('getTagData2', jsonData, 'data')
        
    def getTagData2(self, tags, **constraints):
        """Similar method to getTagData, but interprets maxSize paramater differently.
        In getTagData2, maxSize is per tag rather than the total across all tags

        Constraints defines the range and type of data returned:
            startTime: (str) Earliest time; tradtional or relative date/times
            endTime: (str) Latest time; traditional or relative date/times
            aggregateName: (str) Function to apply to data (call getAggregates for available options)
            aggregateInterval: (str) Interval to apply for function; traditional or relative time spans
            includeQuality: (bool: false) Include the value's quality code
            includeBounds: (bool: false) Include bounding values for Raw Data calls
            useTimeExtension: (bool: true) Retrieve time extended timestamp for last value calls
            quality: (str) Quality of data to return for last value calls ('any', 'good', 'non-bad')
            maxSize: (int:10000) Maximum number of values to return per tag
        """
        # Add timezone handling if not already set via userToken
        if 'timezone' not in constraints and not self._username:
            constraints['timezone'] = 'UTC'  # Default to UTC if not specified

        # Handle new parameters
        if 'useTimeExtension' not in constraints:
            constraints['useTimeExtension'] = True  # Defaults to true in v2

        # If quality is specified and not 'any', force useTimeExtension to false
        if 'quality' in constraints and constraints['quality'] != 'any':
            constraints['useTimeExtension'] = False

        # User friendly conversion
        userFriendlyAutoConversions = [
            ('startDate', 'startTime'),
            ('start', 'startTime'),
            ('endDate', 'endTime'),
            ('end', 'endTime'),
        ]
        for fromKey, toKey in userFriendlyAutoConversions:
            if fromKey in constraints:
                constraints[toKey] = constraints[fromKey]
                del constraints[fromKey]

        # If only a single tag path was provided, simply return values
        if isinstance(tags, str):
            tagPath = tags
            try:
                values = []
                for valueChunk in self._getTagData2([tagPath], **constraints):
                    # Add debug output
                    print(f"Debug - valueChunk: {valueChunk}")

                    # Handle the new response format where each value is an object with t and v properties
                    if tagPath in valueChunk:
                        for item in valueChunk[tagPath]:
                            if isinstance(item, dict) and 't' in item and 'v' in item:
                                # Extract time and value from the object
                                t = item['t']
                                v = item['v']
                                # Quality might be included or might be None/missing
                                q = item.get('q', None)
                                values.append(Tvq(t, v, q))
                return values
            except Exception as e:
                print(f"Error in getTagData2: {str(e)}")
                return []
        else:
            tagData = {tagPath: [] for tagPath in tags}
            try:
                for tagChunk in self._getTagData2(tags, **constraints):
                    # Add debug output
                    print(f"Debug - tagChunk: {tagChunk}")

                    for tagPath in tags:
                        if tagPath in tagChunk:
                            for item in tagChunk[tagPath]:
                                if isinstance(item, dict) and 't' in item and 'v' in item:
                                    # Extract time and value from the object
                                    t = item['t']
                                    v = item['v']
                                    # Quality might be included or might be None/missing
                                    q = item.get('q', None)
                                    tagData[tagPath].append(Tvq(t, v, q))

                return ((tagPath, tagData.get(tagPath, [])) for tagPath in tags)
            except Exception as e:
                print(f"Error in getTagData2: {str(e)}")
                return ((tagPath, []) for tagPath in tags)


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
            justThatTagMaam = isinstance(tags, str)
                
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

    def _getAnnotations(self, tags, startTime, endTime, **constraints):
        """Low-level method to call the getAnnotations API endpoint."""
        jsonData = {
            'userToken': self.userToken,
            'tags': self._coerceToList(tags),
            'startTime': startTime,
            'endTime': endTime
        }
        jsonData.update(constraints)
        return self._iterPost('getAnnotations', jsonData, 'annotations')

    def getAnnotations(self, tags, startTime, endTime, **constraints):
        """Get annotations from requested tags within the given time interval."""
        # Add timezone handling if not already set via userToken
        if 'timezone' not in constraints and not self._username:
            constraints['timezone'] = 'UTC'  # Default to UTC if not specified

        # User friendly conversion for date/time parameters
        userFriendlyAutoConversions = [
            ('startDate', 'startTime'),
            ('start', 'startTime'),
            ('endDate', 'endTime'),
            ('end', 'endTime'),
        ]
        for fromKey, toKey in userFriendlyAutoConversions:
            if fromKey in constraints:
                constraints[toKey] = constraints[fromKey]
                del constraints[fromKey]

        # If only a single tag path was provided, simply return annotations
        if isinstance(tags, str):
            tagPath = tags
            try:
                for annotationChunk in self._getAnnotations([tagPath], startTime, endTime, **constraints):
                    # Add debug output
                    print(f"Debug - annotationChunk: {annotationChunk}")
                    
                    # The response is likely a dict with tagName and annotations properties
                    if isinstance(annotationChunk, dict) and annotationChunk.get('tagName') == tagPath:
                        return annotationChunk.get('annotations', [])
                return []
            except Exception as e:
                print(f"Error in getAnnotations: {str(e)}")
                return []
        else:
            # For multiple tags, collect all annotations
            tagAnnotations = {tagPath: [] for tagPath in tags}
            try:
                for tagPath in tags:
                    for annotationChunk in self._getAnnotations([tagPath], startTime, endTime, **constraints):
                        # Add debug output
                        print(f"Debug - annotationChunk: {annotationChunk}")
                        
                        if isinstance(annotationChunk, dict) and annotationChunk.get('tagName') == tagPath:
                            tagAnnotations[tagPath] = annotationChunk.get('annotations', [])
                return tagAnnotations
            except Exception as e:
                print(f"Error in getAnnotations: {str(e)}")
                return tagAnnotations
        
    def _getTagContext(self, tags, **constraints):
        """Low-level method to call the getTagContext API endpoint."""
        jsonData = {
            'userToken': self.userToken,
            'tags': self._coerceToList(tags)
        }
        jsonData.update(constraints)
        return self._iterPost('getTagContext', jsonData, 'data')
    
    def getTagContext(self, tags, **constraints):
        """Get context for requested tags including both the oldest and latest timestamps."""
        # Add timezone handling if not already set via userToken
        if 'timezone' not in constraints and not self._username:
            constraints['timezone'] = 'UTC'  # Default to UTC if not specified

        # If only a single tag path was provided, simply return its context
        if isinstance(tags, str):
            tagPath = tags
            try:
                for contextChunk in self._getTagContext([tagPath], **constraints):
                    # The response is a dict with tagName and tagContext properties
                    if isinstance(contextChunk, dict) and contextChunk.get('tagName') == tagPath:
                        return contextChunk.get('tagContext', {})
                return {}
            except Exception as e:
                print(f"Error in getTagContext: {str(e)}")
                return {}
        else:
            # For multiple tags, collect all context data
            tagContexts = {tagPath: {} for tagPath in tags}
            try:
                for tagPath in tags:
                    for contextChunk in self._getTagContext([tagPath], **constraints):
                        if isinstance(contextChunk, dict) and contextChunk.get('tagName') == tagPath:
                            tagContexts[tagPath] = contextChunk.get('tagContext', {})
                return tagContexts
            except Exception as e:
                print(f"Error in getTagContext: {str(e)}")
                return tagContexts

    # Error Handling

    def _post(self, apiUrl, jsonData):
        super()._post(apiUrl, jsonData)

        # Check if it failed. If so, reload.
        if self.lastResults['statusCode'] == 'BadLicense':
            raise RuntimeError("The target Canary instance is not licensed for third party View usage.")
        
    def _raiseUnhandledPostError(self, apiUrl, jsonData):
        if self.lastResults['statusCode'] != 'Good':
            if jsonData and 'password' in jsonData:
                jsonData['password'] = '****'
            raise RuntimeError('Canary API call to "%s" had errors: %r.\nData passed: %r' % (
                apiUrl, self.lastResults.get('errors', []), jsonData))