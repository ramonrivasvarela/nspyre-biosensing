"""
    This file runs when the pulsestreamer module is executed as a script.

    Usage:
        > python -m pulsestreamer           - Search for Pulse Streamers.
        > python -m pulsestreamer <SERIAL>  - Search for Pulse Streamer with given SERIAL number.
"""

import pprint
import sys
from pulsestreamer import findPulseStreamers

if __name__ == '__main__':
    if len(sys.argv) > 1:
        serial = sys.argv[1]
        print('Searching for Pulse Streamer', serial)
        pprint.pprint(findPulseStreamers(serial))
    else:
        print('Searching for Pulse Streamers...')
        pprint.pprint(findPulseStreamers())
