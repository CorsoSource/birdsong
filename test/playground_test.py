import os, re
import random, string
from time import sleep

rint = lambda x: random.randint(0,x)
import threading

from java.util import Date

from birdsong import *


# End to end test
testingDataset = 'Testing'

tagPaths = [
     '.'.join([testingDataset, ''.join([random.choice(string.ascii_uppercase) for i in range(6)])])
    for _ in range(3)
]
print('%-80s' % ('Tags used in the test' + '  ' + 100*'=',))
print(tagPaths)


# Get view setup

# Get view names
print('%-80s' % ('View names' + '  ' + 100*'=',))
with CanaryView() as view:
    for node in view.browseNodes():
        print(node)

# Get datasets in view
print('%-80s' % ('Datasets in view' + '  ' + 100*'=',))
with CanaryView() as view:
    for node in view.browseNodes('CS-Surface61'):
        print(node)

# Autoresolve for testing
print('%-80s' % ('Main view' + '  ' + 100*'=',))
def getTestingNode():
    with CanaryView() as view:
        for node in view.browseNodes():
            for dataset in view.browseNodes(node):
                if dataset == 'Testing':
                    return node
mainView = getTestingNode()
print(mainView)


tvqDict = {
    tagPaths[0]: [
        ('2019-10-01T01:23:45Z', 1.23),
        ('2019-10-01 02:34:56Z', 2.34,192),
        Tvq('2019-10-01T03:45:01Z', 3.45),
        Tvq('2019-10-01T04:56:12Z', 4.56,192),
    ]
}

with CanarySender() as send:
    send.storeData(tvqDict)
    

tagPath = mainView + '.' + tagPaths[0]
print('%-80s' % ('One tag - data' + '  ' + 100*'=',))
print(tagPath)
    

# Get the default value (most recent - will be the No Data value)
with CanaryView() as view:
    for value in view.getTagData(tagPath):
        print(value)
        
print('%-80s' % ('... and filtered' + '  ' + 100*'=',))
# Get multiple values
with CanaryView() as view:
    for value in view.getTagData(tagPath, 
                                 startTime='2019-10-01T00:00:00-0700',
                                 endTime='2019-10-01T03:00-0700'):
        print(value)
    
    
tvqDict = {
    tagPaths[1]: [
        ('2019-10-01T01:11:11Z', 1.11),
        ('2019-10-01 02:22:22Z', 2.22, 192),
        Tvq('2019-10-01 03:33:33Z', 3.33),
        Tvq('2019-10-01 04:44:44Z', 4.44, 192),
    ],
    tagPaths[2]: [
        ('2019-10-01 01:00:00Z', 1),
        ('2019-10-01 02:00:00Z', 2, 192),
        Tvq('2019-10-01 03:00:00Z', 3),
        Tvq('2019-10-01 04:00:00Z', 4, 192),
    ]
}

with CanarySender() as send:
    send.storeData(tvqDict)
    
print('%-80s' % ('Multiple tag list' + '  ' + 100*'=',))
tagList = [mainView + '.' + tagPath for tagPath in tagPaths[1:3]]
print(tagList)

print('%-80s' % ('Multiple tag values' + '  ' + 100*'=',))
# Get the default value (most recent - will be the No Data value)
with CanaryView() as view:
    for tagPath, values in view.getTagData(tagList):
        print(tagPath)
        for value in values:
            print('\t%r' % value)
    
    
print('%-80s' % ('... and filtered' + '  ' + 100*'=',))
# Get the values for each tag between given dates
with CanaryView() as view:
    for tagPath, values in view.getTagData(tagList, 
                                           start='2019-10-01T00:00:00-0700',
                                           end='2019-10-01T03:00-0700'):
        print(tagPath)
        for value in values:
            print('\t%r' % value)
            

testDuration = 10
testInterval = 2


def generateData(tagPaths=tagPaths, duration=testDuration, interval=testInterval):
    
    with CanarySender() as send:
        for step in range(testDuration//interval):

            tvqDict = {}
            
            for ix,tagPath in enumerate(tagPaths):
                tvqDict[tagPath] = [ Tvq(Date(), 100*step + ix) ]

            send.storeData(tvqDict)
            
            sleep(interval)
    
print('%-80s' % ('Simulcast: one tag' + '  ' + 100*'=',))
t1 = threading.Thread(target=generateData, args=([tagPaths[0]],))
t1.start()
    
    
stepTime = 3

with CanaryView() as view:
    for step in range( (testDuration//stepTime) + 2):
        print('Update %d' % step)
        for value in view.getLiveData(mainView + '.' + tagPaths[0]):
            print(value)
        sleep(stepTime)
        

print('%-80s' % ('Simulcast: multiple tags' + '  ' + 100*'=',))   
# Only update the tags after the first
t2= threading.Thread(target=generateData, args=(tagPaths[1:],))
t2.start()


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
    
    
    
    
    
    
    
    
    
    
    
    




