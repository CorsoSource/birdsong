# Birdsong - A Python interface to the Canary API
_Make talking to Canary easy_

[Canary](https://canarylabs.com/en/products/historian) is a historian from [Canary Labs](https://github.com/CanaryLabs), and `birdsong` is a library for interfacing with it via Python.

Birdsong will take care of the details of dealing with REST calls, tokens, continuations, and other powerful low level features to let you focus on making Canary sing.

## Table of Contents

 - [Installation](#installation)
 - [Quickstart](#quickstart)
 - [Usage](#usage)
   - [Helper structures](#helper-structures)
   - [Sending data to Canary: `CanarySender`](#sending-data-to-canary-canarysender)
     - [Create new file: `createNewFile`](#create-new-file-createnewfile)
     - [Create rollover file: `fileRollover`](#create-rollover-file-filerollover)
     - [Store data: `storeData`](#store-data-storedata)
   - [Viewing data in Canary: `CanaryView`](#viewing-data-in-canary-canaryview)
     - [Exploring Canary: `browseNodes`](#exploring-canary-browsenodes)
     - [Exploring tags: `browseTags`](#exploring-tags-browsetags)
     - [Get node status: `browseStatus`](#get-node-status-browsestatus)
     - [Option values: translate quality values: `getQualities`](#option-values-translate-quality-values-getqualities)
     - [Option values: get aggregate values: `getAggregates`](#option-values-get-aggregate-values-getaggregates)
     - [Get tag data: `getTagData`](#get-tag-data-gettagdata)
     - [Get tag properties: `getTagProperties`](#get-tag-properties-gettagproperties)
     - [Get *live* tag data: `getLiveData`](#get-live-tag-data-getlivedata)
 - [Advanced usage](#advanced-usage)
 - [Contributing](#contributing)
 - [License](#license)

## Installation

### Pip

You can use the packages on the PyPI via pip:
```bash
python -m pip install birdsong --upgrade
```

### Manual installation
Copy the contents of the Canary folder into your `site-packages` folder in your Python `libs` folder.
Depending on your environment, use the Git branch appropriate. 


### Ignition


Choose the branch for the version of Ignition in use first. From there you may either:

A) Copy the `/birdsong` directory from this repo into directly into Ignition's `./user-lib/pylib/site-packages/` directory.
On Windows systems this will likely be `C:\Program Files\Inductive Automation\Ignition\user-lib\pylib\site-packages`

B) Copy the contents of the all-in-one python file into the project library in the Ignition Designer.
That file will be named something like `birdsong.ignition_8.py`.

Once copied, the install can be tested with the `./test/playground_test.py` file in that branch. 
(Change the import path if Birdsong was places somewhere other than `site-packages` or in `Project Library/birdsong`)

## Quickstart

```python
# get started so quick we don't even have time for text outside a code block
from birdsong import CanarySender, CanaryView, Tvq

viewName = 'CS-Surface61'
datasetName = 'Testing2'
tagPath = datasetName + '.Quick Data!!!'
with CanarySender(autoCreateDatasets=True) as sender:
    sender.storeData({tagPath: [Tvq('2019-10-20 12:34Z', -666), Tvq('2019-10-20 15:20Z', 999)]})
    
    with CanaryView() as view:
        print(next(view.getTagData(viewName + '.' + tagPath)))
```
> ``` 
> {'timestamp': u'2019-10-20T15:20:00.0000000-07:00', 'value': 999}
> ```

In this we:
- Imported the Canary interfaces and a convenient helper
- Connected to the localhost Canary Sender service on the default anonymous port
- Stored two datapoints in the `Quick Data!` tag in the `Testing2` dataset (whether or not `Testing` already existed - it does _now_)
- Connected to the localhost Canary View service on the default anonymous port
- Got data from the `CS-Surface61` view (the name my computer gave my historian)...
- ... and immediately consumed the first entry returned via Python's `next` keyword...
- ... and printed it to the console (which the `Tvq` class autoformatted to look like a dictionary)
- And after the `with` statements, Python exited the connections (first `view` then `sender`), revoking tokens as needed to free them up for others to use.

> Inside baseball note: if the `view` was initialized outside the sender service's context (the `with` statement), the value returned would have been `None`, since we didn't tell the sender service to set `autoWriteNoData=False`. Thus, once the `with` ends the sender would have automatically marked an end to the data transmission session via a `No Data` entry. Pass in the flag to suppress that, if desired.

## Important security notice: `noVerifySSL=False` by default

Because many Canary instances are on intranets and may or may not have certificates that are easily validated by a trusted central authority, SSL validation is *OFF by default*.

You may keep warnings on if you set `birdsong.rest.VALIDATE_SSL_CERTS = True` before initializing a connection to Canary. You may also manually turn on cert validation by passing in `verifySSL=True` to `CanaryView` and `CanarySender` on initialization.

## Usage

By default, the connections will attach to `localhost` over an anonymous connection. If you're testing `birdsong` on the same machine as a Canary instance, it'll try to connect to that first.

Tokens will be aquired as needed. That means until a call is made that requires it, it won't request a user token. Further, it will keep trying to use the token until Canary throws an error on it; on token expiration, Canary will send an error and the interface class will automatically reaquire. You won't see the error other than a slight additional delay as the new token is reaquired.

Both `CanaryView` and `CanarySender` are designed to automatically clean themselves up when they go out of scope. For best practice, use it in a [context manager](https://book.pythontips.com/en/latest/context_managers.html) Once instantiated, it will make the HTTP REST calls to Canary with the right user/session/livedata tokens. If they expire, it'll renew them on the next call.

> For the purposes of the following examples, assume that Canary is running on `localhost`, and that machine is called `CS-Surface61`. Examples of how to log in will be sprinkled throughout as well. 
> Also assume that there is a dataset called `Testing` in which we'll be putting and pulling most of the data in the following examples.

For demo purposes, we'll assume that `Testing` is the dataset of choice, and our main view will be `CS-Surface61`:
```python
import random, string

host     = 'localhost'
mainView = 'CS-Surface61'
dataset  = 'Testing'

tagPaths = [
     '.'.join([dataset, ''.join([random.choice(string.ascii_uppercase) for i in range(6)])])
    for _ in range(3)
]
print(tagPaths)
```
> ```
> ['Testing.ADRLCO', 'Testing.XBCFZF', 'Testing.ITKORQ']
> ```

For demo purposes, I'll be referencing these tags, unless stated otherwise.

### Helper structures

Three helper classes are provided: `Tvq`, `Property`, and `Annotation`. These are all based on a class that allow these to be created with a bit of flexibility. Importantly, these will ensure values are sent to Canary in the expected order while leaving optional values out.

> Note: If Canary returns a date of `0001-01-01T00:00:00.0000000` this will be set on the `timestamp` fields as `None`. It's a value returned under some circumstances (like requesting data for a nonexistent tag in a valid dataset), but because it's not a valid time `birdsong` interprets this to make sure it can't be confused for a normal datetime object.

To generate an instance, pass in values either in order or by name:

```python
>>> tvq1 = Tvq('2019-10-01 03:00:00', 3) # quality is optional and assumed 192 GOOD
>>> tvq2 = Tvq('2019-10-01 12:34:56', 999, 216)
>>> tvq1
{'timestamp': '2019-10-01 03:00:00', 'value': 3}
>>> tvq2
{'timestamp': '2019-10-01 12:34:56', 'quality': 216, 'value': 999}
>>> tvq1.quality
None
>>> tvq2.value
999
>>> tvq2.v
999
>>> tvq2['value']
999
>>> Tvq('0001-01-01T00:00:00.0000000-08:00',None)
{'timestamp': None, 'value': None}
```

The values for these are:

| Helper Class | Attributes |
| ---- | ---- |
| Tvq | `timestamp`, `value`, `quality`* |
| Property | `name`, `timestamp`, `value`, `quality` * |
| Annotation | `user`, `timestamp`, `value`, `createdAt`* |
> `*` are optional

Note that these will attempt to convert the timestamp to an [Arrow](https://arrow.readthedocs.io/en/latest/) datetime object. It's just like a normal `datetime` object, but a bit smarter and easier to manipulate. Combined with [ciso8601](https://github.com/closeio/ciso8601), this can quickly convert the timestamps to a highly flexible object.

Each class has a settter like `Tvq.setTimeFormat('...')` that can be called in case something perverse like a _non_-ISO8601 date is parsed. Note that a timezone should be set. Canary returns results in a timezone sensitive way - *be _ever_ wary of naked timestamps, especially when searching, filtering, and storing data!*

Also note that once instantiated these are _immutible_. These are meant to be treated as read-only since no mechanism to feed directly back on the process is available.

### Sending data to Canary: `CanarySender`

The `CanarySender` class works just like how views are worked with. 

#### Create new file: `createNewFile`

Use this to create a new file that's not linked to the previous. Provide it with the dataset that gets a new file and the timestamp to apply to the file.

```python
with CanarySender() as send:
    send.createNewFile('Testing', '2019-10-01 00:00')
```

#### Create rollover file: `fileRollover`

Create a new file rolling over from the previous.

```python
with CanarySender() as send:
    send.fileRollover('Testing', '2019-10-01 00:00')
```

#### Store data: `storeData`

The `storeData` method logs both tvq values (time, value, quality) as well as properties and annotations. If there is any question about the tuples that should be sent to Canary, use the helper structs - these will be expanded correctly when sent.

All inputs are dictionaries where the keys are Canary tag paths and the values are lists of entries.

Storing data is as easy as making a dictionary of tags and a list of their TVQ entries.

```python
tvqDict = {
    tagPaths[1]: [
        ('2019-10-01 01:11:11', 1.11),
        ('2019-10-01 02:22:22', 2.22, 192),
        Tvq('2019-10-01 03:33:33', 3.33),
        Tvq('2019-10-01 04:44:44', 4.44, 192),
    ],
    tagPaths[2]: [
        ('2019-10-01 01:00:00', 1),
        ('2019-10-01 02:00:00', 2, 192),
        Tvq('2019-10-01 03:00:00', 3),
        Tvq('2019-10-01 04:00:00', 4, 192),
    ]
}

with CanarySender() as send:
    send.storeData(tvqDict)
```

Store properties like so:
```python
with CanarySender() as send:
    send.storeData(properties={
        tagPaths[0]: [['Some Property', '10/01/2019 12:00', 'A property value']]
    })
```
> See the `getTagProperties` example for getting this back from the system.

And annotations likewise:

```python
with CanarySender() as send:
    send.storeData(annotations={
        tagPaths[0]: [['SHODAN', '11/7/2019 19:11', 'Passcode 711 missing']]
    })
```


### Viewing data in Canary: `CanaryView`

Views are how we look into the data Canary holds. The interface `birdsong` provides is the `CanaryView` class. 

Pass in the following keywords to 


#### Exploring Canary: `browseNodes`

If my main Canary instance is on my computer (named `CS-Surface61`), then `browseNodes` will list the  
```python
from birdsong import CanaryView

with CanaryView() as view:
	for node in view.browseNodes():
		print(node)
```
> ```
> Test Model
> CS-Surface61
> ```

Likewise, we can drill in to get the datasets under a view:
```python
with CanaryView() as view:
	for node in view.browseNodes('CS-Surface61'):
		print(node)
```
> ```
> Testing
> {Diagnostics}
> ```

#### Exploring tags: `browseTags`

A tag listing can be retrieved by calling `browseTags`. The `path` argument is the root node to search under, while `search` will narrow the results down to values matching the tag (much as the search works in Axiom). Set `deep` to `True` to recursively search a node.

```python
with CanaryView() as view:
    for tagPath in view.browseTags(path='CS-Surface61.Testing'):
        print tagPath
```
> ```
> CS-Surface61.Testing.ADRLCO
> CS-Surface61.Testing.ITKORQ
> CS-Surface61.Testing.XBCFZF
> ```
> 

My computer happens to have another testing dataset, which shows up in the following:
```python
with CanaryView() as view:
    for tagPath in view.browseTags(path='CS-Surface61', search='Testing', deep=True):
        print tagPath
```
> ```
> CS-Surface61.Testing.BKYTXS
> CS-Surface61.Testing.FEZWZR
> CS-Surface61.Testing.OCEGGC
> CS-Surface61.Testing.QIFAFZ
> CS-Surface61.Testing.RWNNHP
> CS-Surface61.Testing.Some.Tag.Path.CV
> CS-Surface61.Testing2.Quick Data!!!!
> ```


#### Get node status: `browseStatus`

To find out if a node has been updated, directly query it and check if the sequence number is different:
```python
>>> print(CanaryView().browseStatus('CS-Surface61'))
```
or muliple views at once:
```python
with CanaryView() as view:
    for viewName,sequence in view.browseStatus(['CS-Surface61','Test Model']):
        print('%s  -  %s' % (viewName, sequence))
```
> ```
> 637078138670000000  -  CS-Surface61
> 637075536560000000  -  Test Model
> ```


#### Option values: translate quality values: `getQualities`

Unless a returned value is `192` (`Good`), data is returned with a quality value. This is a value as enumerated by the OPC communication standard. Not everyone has all the values memorized, though, so you can look them up with this function.

```python
with CanaryView(host='localhost') as view:
    print view.getQualities('90')
```
> ```
> {u'90': u'Uncertain-Sub Normal-Limit High'}
> ```

Or you can ask for more than one at a time (say from retrieved data)

```python
someDataQualities = [value.quality for value in someData if value.quality]

with CanaryView() as view:
    print view.getQualities(someDataQualities)
```
> ```
> {u'9': u'Bad-Not Connected-Limit Low', u'90': u'Uncertain-Sub Normal-Limit High', u'210': u'Good-Limit High'}
> ```

#### Option values: get aggregate values: `getAggregates`

When getting data for a tag, you can set `aggregateName` to one of the values given by this dictionary.

```python
with CanaryView() as view:
    print(sorted(view.getAggregates().keys()))
```
>```
> [u'Average', u'Count', u'Delta', u'DeltaBounds', u'DurationBad', u'DurationGood', u'DurationInStateNonZero', u'DurationInStateZero', u'End', u'EndBound', u'Instant', u'Interpolative', u'Maximum', u'Maximum2', u'MaximumActualTime', u'MaximumActualTime2', u'Minimum', u'Minimum2', u'MinimumActualTime', u'MinimumActualTime2', u'NumberOfTransitions', u'PercentBad', u'PercentGood', u'Range', u'Range2', u'StandardDeviationPopulation', u'StandardDeviationSample', u'Start', u'StartBound', u'TimeAverage', u'TimeAverage2', u'Total', u'Total2', u'TotalPer24Hours', u'TotalPerHour', u'TotalPerMinute', u'VariancePopulation', u'VarianceSample', u'WorstQuality', u'WorstQuality2']
> ```

#### Get tag data: `getTagData`

To get the most recent value for a tag, simply call `getTagData` with that tag's path:

```python
# Get the default value (most recent - may well be the No Data value)
with CanaryView() as view:
	for value in view.getTagData('CS-Surface61.Testing.ADRLCO'):
		print(value)		
```
> ```
> {'timestamp': u'2019-10-01T04:56:12.0000001-07:00', 'value': None}
> ```

> Note: as we log data to Canary and close our sessions, Canary will assume the data stream has come to an end and bracket it with `No Data`, which will show as a `None` in our results here.

To get the values for a tag between two time spans, simply pass in the constraints as arguments:

```python
# Get all values between dates
tagPath = mainView + '.' + dataset + '.' + 'ADRLCO'

with CanaryView() as view:
    for value in view.getTagData(tagPath, 
                                 startTime='2019-10-01T00:00:00-0700',
                                 endTime='2019-10-01T03:00-0700'):
        print(value)
```
> ```
> {'timestamp': u'2019-10-01T01:23:45.0000000-07:00', 'value': 1.23}
> {'timestamp': u'2019-10-01T02:34:56.0000000-07:00', 'value': 2.34}
> ```

Any of the constraints outlined in your Canary View's `/help` endpoint will work.

Getting data for more than one tag simply means passing in a list of tags.
```python
tagList = [mainView + '.' + tagPath for tagPath in tagPaths[1:3]]

# Get the default value (most recent - will be the No Data value)
with CanaryView() as view:
    for tagPath, values in view.getTagData(tagList):
        print(tagPath)
        for value in values:
            print('\t%r' % value)
```
> ```
> CS-Surface61.Testing.XBCFZF
> 	{'timestamp': u'2019-10-01T04:44:44.0000001-07:00', 'value': None}
> CS-Surface61.Testing.ITKORQ
> 	{'timestamp': u'2019-10-01T04:00:00.0000001-07:00', 'value': None}
> ```

Pay special attention that the results match the input: if a tag path is given by itself, you'll get back an iterable of values. If a list of tags are given, you'll get back an iterable back of the tag paths and their values. (These will be in the same order given.) 

If a start and end time is given it will look like this:
```python
# Get the values for each tag between given dates
with CanaryView() as view:
    for tagPath, values in view.getTagData(tagList, 
                                           start='2019-10-01T00:00:00-0700',
                                           end='2019-10-01T03:00-0700'):
        print(tagPath)
        for value in values:
            print('\t%r' % value)
```
> ```
> CS-Surface61.Testing.XBCFZF
> 	{'timestamp': u'2019-10-01T01:11:11.0000000-07:00', 'value': 1.11}
> 	{'timestamp': u'2019-10-01T02:22:22.0000000-07:00', 'value': 2.22}
> CS-Surface61.Testing.ITKORQ
> 	{'timestamp': u'2019-10-01T01:00:00.0000000-07:00', 'value': 1}
> 	{'timestamp': u'2019-10-01T02:00:00.0000000-07:00', 'value': 2}
> ```

Note that `start` and `end` were used here. For convenience these are automatically translated to the naming convention Canary expects. (I caught myself writing the wrong suffix too much...)

```python
with CanaryView() as view:
    tagProps = view.getTagProperties('CS-Surface61.' + tagPaths[0])
    print(tagProps)
```
> ```
> {u'Some Property': u'A property value'}
> ```
> Note that this result comes from the later `storeData` routine.

Passing in a list results in a generator:

```
tagList = ['CS-Surface61.' + tagPath for tagPath in tagPaths[:2]]
with CanaryView() as view:
    for tagPath, propDict in view.getTagProperties(tagList):
        print('%s - %r' % (tagPath, propDict))
```
> ```
> CS-Surface61.Testing.QIFAFZ - {u'Some Property': u'A property value'}
> CS-Surface61.Testing.OCEGGC - {}
> ```


#### Get tag properties: `getTagProperties`

Tag properties can be queried by the `getTagProperties` function. This will return the most recent value set for each property for a tag.

Like the other `get` iterator methods, this will likewise return a dict object or a generator when a list of tag paths is provided.


#### Get *live* tag data: `getLiveData`

Canary provides a special API call for getting the most recent data _since the last time you asked_ in the `getLiveData` method. Birdsong will manage the token needed to take advantage of this.

The easiest way to use it is like the regular tag data method:
```python
tagPath = '.'.join([mainView, dataset, tagPaths[0]])

with CanaryView() as view:
    for value in view.getLiveData(tagPath):
		print(value)
```
> ```
> {'timestamp': u'2019-10-27T16:03:10.4280000-07:00', 'value': 0}
> ```

This tag happens to have another thread pumping data in via `CanarySender().storeData()`, so if we connect and check periodically we'll see additional updates as they come in:
```python
stepTime = 3

with CanaryView() as view:
    for step in range( (testDuration//stepTime) + 2):
        print('Update %d' % step)

        for value in view.getLiveData(tagPath):
            print(value)

        sleep(stepTime)
```
> ```
> Update 0
> {'timestamp': u'2019-10-27T16:03:12.4490000-07:00', 'value': 100}
> Update 1
> {'timestamp': u'2019-10-27T16:03:14.4590000-07:00', 'value': 200}
> {'timestamp': u'2019-10-27T16:03:16.4690000-07:00', 'value': 300}
> Update 2
> {'timestamp': u'2019-10-27T16:03:18.4740000-07:00', 'value': 400}
> Update 3
> {'timestamp': u'2019-10-27T16:03:18.4740001-07:00', 'value': None}
> ```

Likewise, multiple tags can also be checked. For this example, we'll only be updating tags that _aren't the first_. 
```python
# Check all tags so that we can see the first _not_ get updated in later calls

viewQualifiedTagPaths = [mainView + '.' + tagPath for tagPath in tagPaths]
stepTime = 3

with CanaryView() as view:
    for step in range( (testDuration//stepTime)+2):
        print('Update %d' % step)

        for tagPath,values in view.getLiveData(viewQualifiedTagPaths):
            print('\t%s' % tagPath)

            for value in values:
                print('\t\t%r' % value)
        sleep(stepTime)
```
> ```
> Update 0
> 	CS-Surface61.Testing.ITKORQ
> 		{'timestamp': u'2019-10-27T16:02:39.4040000-07:00', 'value': 1}
> 	CS-Surface61.Testing.ADRLCO
> 		{'timestamp': u'2019-10-27T16:00:52.1000001-07:00', 'value': None}
> 	CS-Surface61.Testing.XBCFZF
> 		{'timestamp': u'2019-10-27T16:02:39.4040000-07:00', 'value': 0}
> Update 1
> 	CS-Surface61.Testing.ITKORQ
> 		{'timestamp': u'2019-10-27T16:02:41.4190000-07:00', 'value': 101}
> 	CS-Surface61.Testing.XBCFZF
> 		{'timestamp': u'2019-10-27T16:02:41.4190000-07:00', 'value': 100}
> Update 2
> 	CS-Surface61.Testing.ITKORQ
> 		{'timestamp': u'2019-10-27T16:02:43.4390000-07:00', 'value': 201}
> 		{'timestamp': u'2019-10-27T16:02:45.4500000-07:00', 'value': 301}
> 	CS-Surface61.Testing.XBCFZF
> 		{'timestamp': u'2019-10-27T16:02:43.4390000-07:00', 'value': 200}
> 		{'timestamp': u'2019-10-27T16:02:45.4500000-07:00', 'value': 300}
> Update 3
> 	CS-Surface61.Testing.ITKORQ
> 		{'timestamp': u'2019-10-27T16:02:47.4560000-07:00', 'value': 401}
> 	CS-Surface61.Testing.XBCFZF
> 		{'timestamp': u'2019-10-27T16:02:47.4560000-07:00', 'value': 400}
> ```

Note that `CS-Surface61.Testing.ADRLCO` didn't show up past the first loop iteration. That's because the tag had no new data (and the `None` is the result of that - the other two's last update would have shown the same had it been let go one more iteration.)


## Advanced usage

Given this is Python, we can do a number of handy things.

For example, we can predefine values for configurations and use `**kwarg` expansion to map the configuration dict values to the function.

```python
# Send a random number to a tag every 5 seconds forever
from birdsong import CanarySender, Tvq, Annotation
import random
import arrow

senderConfig = {
	'username': 'AzureDiamond',
	'password': 'hunter2',
	'autoCreateDatasets': True,
	'autoWriteNoData': False
}

tagPath = 'CS-Surface61.Testing.Random Noise'

with CanarySender(**senderConfig) as send:

	rightNow = arrow.utcnow().isoformat()

	updateData = {
		'tvqs': {tagPath: (rightNow, random.random())},
		'annotations': {tagPath: (senderConfig['username'],rightNow,'Inserted Data')}
	}

    send.storeData(**updateData)

    sleep(5)
```

(Don't use annotations like this, though...)

You can also use the interfaces outside of a context manager. When the object goes out of scope it'll get the connection tokens cleaned up automatically. Note that this will _not_ guarantee cleanup in the event the program shuts down gracelessly (but it'll try, given the chance).

For example, you may want to initiate your live data connection, but not close it. Or you just don't want to indent everything. And, just to be sure, you can close the connection yourself using `__exit__`. Or to be brutal, go ahead and use the `del` command.

```python
from birdsong import CanaryView
import arrow

# Create the object.
view = CanaryView()

tagSetOne = [
	'CS-Surface61.Testing.Test Tag 1', 
	'CS-Surface61.Testing.Test Tag 2'
]

tagSetTwo = [
	'CS-Surface61.Testing.Some Other Tag'
]

loopCount = 0
while True:
    print('Update %d' % loopCount)

    for tagPath,values in view.getLiveData(tagSetOne):
        print('\t%s' % tagPath)
        for value in values:
            print('\t\t%r' % value)

    for tagPath,values in view.getLiveData(tagSetTwo):
        print('\t%s' % tagPath)
        for value in values:
            print('\t\t%r' % value)

    sleep(stepTime)

# Manually close out the connection
view.__exit__()
```

## Contributing

Feel free to send suggestions and bug notices (especially if the API shifts/upgrades and is not caught quickly). Features requests are also welcome, though this is primarily meant to act as an interface wrapper library rather than an extension (though 'unpythonic' constructs will be considered bugs :)

## License

[Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0)
