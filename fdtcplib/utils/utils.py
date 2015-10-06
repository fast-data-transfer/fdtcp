"""
Helper routines.

__author__ = Zdenek Maxa

"""


import os
import datetime
import random

from psutil import Process



def getHostName():
    """
    Returns hostname.
    
    """
    host = os.getenv("HOSTNAME", None) or os.uname()[1] 
    return host


def getUserName():
    user = os.getenv("LOGNAME", None) or "unknownuser"
    return user
    

def getRandomString(start, stop, num):
    """
    Returns random string chosen from a sequence starting at
    start, ending with stop. start/stop must be characters,
    num is length of the result random sequence.
    ord(stop) > ord(start)
    
    """
    startInt = ord(start)
    stopInt = ord(stop)
    r = ""
    for i in range(num):
        c = random.randrange(startInt, stopInt)
        r = "".join([r, chr(c)])    
    return r


def getDateTime():
    """
    Returns date and time in format
    year-month-day-hour-minute-second-microsecond.
    
    """
    n = datetime.datetime.now()
    format = "%s-%s-%s-%sh:%sm:%ss"
    toAlign = (n.year, n.month, n.day, n.hour, n.minute, n.second)
    aligned = ["%02d" % i for i in toAlign]
    r = format % tuple(aligned)
    return r


def getOpenFilesList(offset=4):
    """
    Returns all currently open files.
    Problem: #41 - Too many open files (fdtd side)
    
    """
    myPid = os.getpid()
    proc = Process(myPid)
    files = proc.get_open_files()
    filesStr = "\n".join(["%s%s (fd=%s)" % (offset * ' ', f.path, f.fd)
               for f in files])
    numFiles = len(files)
    return numFiles, filesStr
