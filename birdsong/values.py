# Internally, all timestamps will be held as the OffsetDateTime objects.
# It maintains precision, can be manipulated, and writes back as ISO8601.
# TL;DR: OffsetDateTime is the least worst solution that doesn't involve
#        dragging in an external library.
# Instant is included because 
from java.time import OffsetDateTime, Instant
from java.time.format import DateTimeFormatter
from java.text import SimpleDateFormat


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


