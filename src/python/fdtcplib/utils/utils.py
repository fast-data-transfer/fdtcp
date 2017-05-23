"""
Helper routines.
"""
import os
import datetime
import random
from psutil import Process


def getId(srcHostName, dstHostName):
    """
    Transfer job / request / id will consist of hostname of the
    machine fdtcp is invoked on and timestamp. This id will be used
    in all requests to fdtd for tracking the state of the transfer
    job, esp. by MonALISA ApMon.
    Transfers at fdtd will be associated with this ID - make it as
    unique as possible to avoid collisions.
    """
    hostname = getHostName()
    # u = getUserName()
    currentDate = getDateTime()
    randomStr = getRandomString('a', 'z', 5)
    template = "fdtcp-%(host)s--%(source)s-to-%(dest)s--%(datetime)s-%(randomStr)s"
    newDict = dict(host=hostname, source=srcHostName, dest=dstHostName,
                   datetime=currentDate, randomStr=randomStr)
    idT = template % newDict
    return idT


def getHostName():
    """
    Returns hostname.

    """
    host = os.getenv("HOSTNAME", None) or os.uname()[1]
    return host


def getUserName():
    """ Get username from env or set as unknownuser """
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
    rand = ""
    for dummyi in range(num):
        character = random.randrange(startInt, stopInt)
        rand = "".join([rand, chr(character)])
    return rand


def getDateTime():
    """
    Returns date and time in format
    year-month-day-hour-minute-second-microsecond.
    """
    timeNow = datetime.datetime.now()
    formatDate = "%s-%s-%s-%sh:%sm:%ss"
    toAlign = (timeNow.year, timeNow.month, timeNow.day, timeNow.hour, timeNow.minute, timeNow.second)
    aligned = ["%02d" % i for i in toAlign]
    retVal = formatDate % tuple(aligned)
    return retVal


def getOpenFilesList(offset=4):
    """
    Returns all currently open files.
    Problem: #41 - Too many open files (fdtd side)
    """
    myPid = os.getpid()
    proc = Process(myPid)
    files = proc.open_files()
    filesStr = "\n".join(["%s%s (fd=%s)" % (offset * ' ', f.path, f.fd)
                          for f in files])
    numFiles = len(files)
    return numFiles, filesStr
