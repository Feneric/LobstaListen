#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SeaHack: Store audio and additional information captured from the sea floor.
"""

from datetime import datetime
from os import chdir
from sys import exit
from syslog import syslog, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG
from argparse import ArgumentParser
from struct import pack
from random import randint
from twisted.internet.task import LoopingCall
from twisted.internet.utils import getProcessOutput
from twisted.internet import reactor
try:
    from gps import gps
    __gpsSession__ = gps()
    __gpsSession__.query('admosy')
except ImportError:
    syslog(LOG_ERR, "No GPS found.")


    class gps:
        """
        This is a dummy gps class filling in for missing GPS.
        """
        pass

    __gpsSession__ = gps()
    __gpsSession__.utc = datetime.now().isoformat()
    __gpsSession__.fix = gps()
    __gpsSession__.fix.latitude = 'No Lat'
    __gpsSession__.fix.longitude = 'No Long'

__interval__ = 360
__duration__ = 3600
__outputDir__ = '/home/eric/Documents/HackToTheSea/Data'
__dataInterval__ = 1
__recordAudioCmd__ = """/usr/bin/arecord -q -t wav -f cd -c 1 -D plughw:1,0 -d {}"""
__compressAudioCmd__ = """/usr/bin/flac -s --best -o {}.flac -"""

def parseArguments(args=None):
    """
    Parse command-line arguments.
    """
    assert args is None or isinstance(args, list)
    # Parse command-line arguments
    parser = ArgumentParser(
        description="Repeatedly record audio for a number of seconds."
    )
    defaultDuration = __interval__
    parser.add_argument(
        '--duration', '-d', default=defaultDuration,
        nargs='?', type=int, const=defaultDuration,
        help='The duration of sound recording in seconds. ' +
        'By default this is {}'.format(defaultDuration)
    )
    defaultInterval = __duration__
    parser.add_argument(
        '--interval', '-i', default=defaultInterval,
        nargs='?', type=int, const=defaultInterval,
        help='The interval of sound recordings in seconds. ' +
        'By default this is {}'.format(defaultInterval)
    )
    defaultOutputDir = __outputDir__
    parser.add_argument(
        '--outputdir', '-o', default=defaultOutputDir,
        nargs='?', const=defaultOutputDir,
        help='The folder in which to store data. ' +
        'By default this is {}'.format(defaultOutputDir)
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Make output more verbose, useful for debugging.'
    )
    return parser.parse_args(args)

def logError(err, verbose=False):
    """
    Log error data to syslog, suitable for errback use.
    """
    errMsg = "Error: {}".format(str(err))
    syslog(LOG_ERR, errMsg)
    if verbose:
        print(errMsg)

def logResponse(retCode, verbose=False):
    """
    Log response data to syslog, suitable for callback use.
    """
    syslog(LOG_INFO, 'Finished recording audio. {}'.format(retCode))
    if verbose:
        print("Recording finished.")

def storeAudio(duration, verbose=False):
    """
    Store a duration's worth of audio.
    """
    outFilename = 'SeaAudio-{}'.format(datetime.now().isoformat())
    syslog(LOG_INFO, 'Recording {} seconds of audio to {}.'.format(duration, outFilename))
    if verbose:
        print("Recording {} seconds of audio to {}...".format(duration, outFilename))
    cmd = __recordAudioCmd__.format(duration) + ' | ' + __compressAudioCmd__.format(outFilename)
    storeResponse = getProcessOutput('/bin/sh', ('-c', cmd))
    storeResponse.addCallback(logResponse, verbose)
    storeResponse.addErrback(logError, verbose)

def cleanup(outFile):
    """
    Cleanup work before shutting down.
    """
    syslog(LOG_INFO, 'Closing sensor data file.')
    outFile.close()
    global __recordAudioLoop__, __recordDataLoop__
    __recordAudioLoop__.stop()
    __recordDataLoop__.stop()

def storeSensorData(outFile):
    """
    Store a sample worth of sensor data.
    """
    sensorReading = randint(0, 65535)  # %FIXME% Obviously this needs to change for real HW
    packedSensorReading = pack('>H', sensorReading)
    outFile.write(packedSensorReading)

# Things to do when this module is directly run.
if __name__ == '__main__':
    args = parseArguments()
    if args.duration + 10 >= args.interval:
        print("The duration must be significantly larger than the interval.")
        exit(1)
    startMsg = 'Recording every {} seconds for {} seconds; storing data in {}'.format(
        args.interval, args.duration, args.outputdir)
    syslog(LOG_INFO, startMsg)
    if args.verbose:
        print(startMsg)
    chdir(args.outputdir)
    try:
        gpsFile = open('Session-{}.txt'.format(datetime.now().isoformat()), 'w')
        gpsFile.write('Latitude: {} Longitude: {} Time: {}'.format(
            __gpsSession__.fix.latitude, __gpsSession__.fix.longitude, __gpsSession__.utc))
        gpsFile.close()
    except IOError as err:
        syslog(LOG_ERR, "Error writing GPS file: {}".format(str(err)))
    try:
        outFile = open('Sensor-{}.hex'.format(datetime.now().isoformat()), 'w')
    except IOError as err:
        syslog(LOG_ERR, "Error writing sensor data file: {}".format(str(err)))
    __recordAudioLoop__ = LoopingCall(storeAudio, args.duration, args.verbose)
    __recordAudioLoop__.start(args.interval)
    __recordDataLoop__ = LoopingCall(storeSensorData, outFile)
    __recordDataLoop__.start(__dataInterval__)
    reactor.addSystemEventTrigger('before', 'shutdown', cleanup, outFile)
    reactor.run()
