"""
	A Python interface to the Canary REST API

"""

name = 'birdsong'

from .view import CanaryView
from .sender import CanarySender
from .values import Tvq, Property, Annotation


__all__ = ['CanaryView', 'CanarySender', 'Tvq', 'Property', 'Annotation']