

class BaseValue(object):

    __slots__ = ('_tuple')

    _fields = ('value')
    _optional = (True)

    def __init__(self, value=None):
        self._tuple = (value,)
    
    @classmethod
    def keys(cls):
        return cls._fields

    def values(self):
        return self._astuple()

    def _astuple(self):
        return tuple(value for value,optional 
                     in zip(self._tuple, self._optional) 
                     if not optional or not (value is None))

    def _asdict(self):
        return dict(zip(self._fields, self))

    def __getitem__(self, key):
        try:
            return self._tuple[key]
        except(TypeError, IndexError):
            return self._tuple[self._ixLookup[key]]

    def __iter__(self):
        return iter(self._astuple())

    def __repr__(self):
        return repr(self._asdict())


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
        self._tuple = (timestamp, value, quality)
    
_finalize(Tvq, 't v q'.split())


class Property(BaseValue):
    _fields = ('name', 'timestamp', 'value', 'quality')
    _optional = (False, False, False, True)

    def __init__(self, name, timestamp, value, quality=None):
        self._tuple = (name, timestamp, value, quality)

_finalize(Property, 'n t v q'.split())


class Annotation(BaseValue):
    _fields = ('user', 'timestamp', 'value', 'createdAt')
    _optional = (False, False, False, True)

    def __init__(self, user, timestamp, value, createdAt=None):
        self._tuple = (user, timestamp, value, createdAt)

_finalize(Annotation, 'u t v c'.split())
    

VALUE_TYPE_MAP = {'tvq': Tvq, 'property': Property, 'annotation': Annotation}
   
def createValue(valueType='tvq', *values):
    return VALUE_TYPE_MAP[valueType.lower()](*values)
