"""A client software for Swabian Instrument's Pulse Streamer 8/2"""

__version__ = '1.7.0'

from pulsestreamer.jrpc import PulseStreamer
from pulsestreamer.enums import ClockSource, TriggerRearm, TriggerStart
from pulsestreamer.sequence import Sequence, OutputState
from pulsestreamer.findPulseStreamers import findPulseStreamers
from pulsestreamer.version import _compare_version_number

__all__ = [
        'PulseStreamer',
        'OutputState',
        'Sequence',
        'ClockSource',
        'TriggerRearm',
        'TriggerStart',
        'findPulseStreamers'
        ]
