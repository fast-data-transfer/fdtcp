"""
Helper routines.
"""
import os
import sys
import apmon
import datetime
import random
import types
import traceback
import linecache
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


def debugDetails(self, indent=4):
    """ Format debug details in nice way """
    rOut = ""
    ind = ' ' * indent
    for k, j in list(list(self.__dict__.items())):
        # not interested in methods
        if isinstance(j, types.MethodType):
            continue
        rOut = ind.join([rOut, "'%s': '%s'\n" % (k, j)])
    return rOut


def getApmonObj(inDest):
    """ Checks if inDest is an object and if not tries to create one."""
    if isinstance(inDest, (str, unicode, basestring)):
        apMonDestinations = tuple(inDest.split(','))
        apMon = apmon.ApMon(apMonDestinations)
        apMon.enableBgMonitoring(True)
        return apMon
    else:
        return inDest


def getTracebackSimple():
    """
    Returns formatted traceback of the most recent exception.
    """
    # sys.exc_info() most recent exception
    trace = traceback.format_exception(*sys.exc_info())
    noExcepResponse = ['None\n']
    # this is returned when there is no exception
    if trace == noExcepResponse:
        return None
    tbSimple = "".join(trace)  # may want to add '\n'
    return tbSimple


def getTracebackComplex(localsLevels=5):
    """
    Returns formatted traceback of the most recent exception.
    Could write into a file-like object (argument would be
    output = sys.stdout), now returns result in formatted string.
    """
    tbComplex = "".join([78 * '-', '\n'])
    tbComplex = "".join([tbComplex, "Problem: %s\n" % sys.exc_info()[1]])

    trace = sys.exc_info()[2]
    stackString = []
    while trace is not None:
        frame = trace.tb_frame
        lineno = trace.tb_lineno
        code = frame.f_code
        filename = code.co_filename
        function = code.co_name
        if filename.endswith(".py"):
            line = linecache.getline(filename, lineno)
        else:
            line = None
        stackString.append((filename, lineno, function, line, frame))
        trace = trace.tb_next

    tbComplex = "".join([tbComplex, "Traceback:\n"])
    localsLevel = max(len(stackString) - localsLevels, 0)
    for i in range(len(stackString)):
        (filename, lineno, name, line, frame) = stackString[i]
        outputLine = (" File '%s', line %d, in %s (level %i):\n" %
                      (filename, lineno, name, i))
        tbComplex = "".join([tbComplex, outputLine])
        if line:
            tbComplex = "".join([tbComplex, "  %s\n" % line])
        if i >= localsLevel:
            # want to see complete stack if exception came from a template
            pass

    tbComplex = "".join([tbComplex, 78 * '-', '\n'])

    del stackString[:]
    frame = None
    trace = None
    return tbComplex
