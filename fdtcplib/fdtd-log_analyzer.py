#!/usr/bin/env python

""""
fdtcp project (aimed at integration of FDT and CMS PhEDEx)

https://twiki.cern.ch/twiki/bin/view/Main/PhEDExFDTIntegration
https://trac.hep.caltech.edu/trac/fdtcp

fdtd-log_analyzer.py - simple log analyzer of the fdtd service logs

tasks / steps:
1) analyze only separate log files (not the main fdtd.log) for the moment,
    mask: *transfer*.log*
2) count "Exit Status: Not OK"
    with TotalBytes, TotalNetworkBytes
3) the same for "Exit Status: OK"
4) "AlreadyBeingCreatedException" occurrences
5) list files which do not have "Logger closing.\n\n\n" at the end
6) search for "Attempt to log into closed log file" messages (issues with
    closed log file)
7) search for 'Address already in use'
8) not CleanupProcessesAction at the end
9) analyze transfer performance at successful transfers

__author__ = Zdenek Maxa

"""


import os
import sys
import fnmatch
import re
import datetime


class AnalysisData(object):
    def __init__(self):
        self.okStatusList = []
        self.notOkStatusList = []
        # list files which are Status: OK but TotalBytes and
        # TotalNetworkBytes are different
        self.okNotMatchingBytes = []
        # calculate TotalBytes for OK, Not OK
        self.okBytes = 0
        self.notOkBytes = 0
        # transfer performance of successful transfers (the same number
        # of items as okStatusList
        self.okRatesList = []
        # AlreadyBeingCreatedException containing log files
        self.alreadyBeingCreated = []
        # "Attempt to log into closed log file" messages
        self.loggerClosedList = []
        # "Address already in use" messages
        self.addressUsedList = []
        # no CleanupProcessesAction at the end
        self.noEndingCleanupList = []
        

def getRate(fd, networkBytes):
    """
    returns performance rate of the corresponding transfer calculated
    from totalNetworkBytes values and time of the transfers. time is
    calculated as difference of the last and first log timestamp.
    
    """
    def getTime(line):
        # the log line looks like this:
        # WARNING   2011-04-24 01:31:13,259 transfer Logger closing.
        stStr = line.split()[1:3]
        dt = stStr[0].split('-')
        tm = stStr[1].split(',')[0].split(':')
        dt.extend(tm)
        dt = datetime.datetime(*[int(i) for i in dt])
        return dt
        
    fd.seek(0)
    lines = fd.readlines()    
    startTimeLine = lines[0]
    # last line of the log file - closing the log file, following are 3x'\n'
    endTimeLine = lines[-4]
    startTime, endTime = getTime(startTimeLine), getTime(endTimeLine)
    duration = endTime - startTime
    megaBytes = networkBytes / 1024.0 / 1024.0
    rate = megaBytes / duration.seconds
    return rate
    

def analyze(logFiles):
    """
    Implementation of above log analyzing tasks ... see above for
    description.
    
    Patterns are:

    TotalBytes: 2818048
    TotalNetworkBytes: 2818048
    Exit Status: OK
    
    or
    
    TotalBytes: 2818048
    TotalNetworkBytes: 10354688
    Exit Status: Not OK
    
    """
    okPattern = ("TotalBytes: (\d*)$\n.*TotalNetworkBytes: "
                 "(\d*)$\n.*Exit Status: OK")
    notOkPattern = ("TotalBytes: (\d*)$\n.*TotalNetworkBytes: "
                    "(\d*)$\n.*Exit Status: Not OK")
    okPattObj = re.compile(okPattern, re.MULTILINE)
    notOkPattObj = re.compile(notOkPattern, re.MULTILINE)
    alreadyPattObj = re.compile("AlreadyBeingCreatedException")
    loggerClosedPattObj = re.compile("Attempt to log into closed log file")
    addressUsedObj = re.compile("Address already in use")
    endingCleanupObj = re.compile("End of request "
                                  "CleanupProcessesAction serving.")
    
    res = AnalysisData()
        
    for fileName in logFiles:
        fd = open(fileName, 'r')
        
        # analyze Exit Status: OK case
        match = okPattObj.search(fd.read())
        if match:
            res.okStatusList.append(fileName)
            totalBytes = int(match.group(1))
            totalNetworkBytes = int(match.group(2))
            if totalBytes != totalNetworkBytes:
                res.okNotMatchingBytes.append(fileName)
            res.okBytes += totalBytes
            rate = getRate(fd, totalNetworkBytes)
            res.okRatesList.append(rate)
                        
        # analyze Exit Status: Not OK case
        fd.seek(0)
        match = notOkPattObj.search(fd.read())
        if match:
            res.notOkStatusList.append(fileName)
            totalBytes = int(match.group(1))
            res.notOkBytes += totalBytes
            
        fd.seek(0)
        match = alreadyPattObj.search(fd.read())
        if match:
            res.alreadyBeingCreated.append(fileName)
            
        fd.seek(0)
        match = loggerClosedPattObj.search(fd.read())
        if match:
            res.loggerClosedList.append(fileName)
            
        fd.seek(0)
        match = addressUsedObj.search(fd.read())
        if match:
            res.addressUsedList.append(fileName)
            
        fd.seek(0)
        match = endingCleanupObj.search(fd.read())
        # count when not present!
        if not match:
            res.noEndingCleanupList.append(fileName)
            
        fd.close()
        
    return res


def fileClosingAnalysis(logFiles):
    """
    Implementation of task 5.
    
    """
    res = []
    for fileName in logFiles:
        fd = open(fileName, 'r')
        lines = fd.readlines()
        # check for: "Logger closing.\n\n\n" at the end of the file
        ending = "Logger closing.\n"
        # after this always follow 3x \n which are not checked here, 
        # just -4th line
        if not lines[-4].endswith(ending):
            res.append(fileName)
        fd.close()
    return res
        

def getFiles(dir):
    """
    Takes into account just current working directory and file
    mask *transfer*.log* - log files for each transfer separately.
    
    """
    toProcess = []
    mask = "*transfer*.log*"
    print "analyzing logs (mask: '%s') in '%s'" % (mask, dir)
    content = os.listdir(dir)
    for f in content:
        if os.path.isfile(f) and fnmatch.fnmatch(f, mask):
            toProcess.append(f)
    print "%s files matching" % len(toProcess)
    return sorted(toProcess)


def myprint(inputList, msg):
    print '-' * 78
    print msg
    for i in inputList:
        print i
    print '\n'


def main():
    # for lists manipulation - consider using sets:
    # e.g. set(dir(list)) - set(dir(tuple))

    print("version of fdtcp: '%s'" % "$Tags: tip $ "
          "(revision $Revision: 3fc511ec82a9 $")
    # take into account just current working directory
    logFiles = getFiles(os.getcwd())
    data = analyze(logFiles)
    notClosed = fileClosingAnalysis(logFiles)
    
    # list log files with neither of above (Status OK, Status not OK)
    notOkNorNotOk = filter(lambda x: (x not in data.okStatusList) and
                                     (x not in data.notOkStatusList),
                                     logFiles)
    
    # list log files 'Exit Status: Not OK' and not
    # containing 'AlreadyBeingCreated'
    # => some other kind of problems
    notOkAndAlreadyBeingCreated = \
        filter(lambda x: (x in data.notOkStatusList) and
                         (x not in data.alreadyBeingCreated), logFiles)
        
    print "total analyzed %s log files\n" % len(logFiles)
    
    gb = data.okBytes / 1024.0 / 1024.0 / 1024.0
    perc = len(data.okStatusList) / (len(logFiles) / 100.0)
    m = ("'Exit Status: OK' files: %s files, %s GB in total, "
         "%s %%, log files:" % (len(data.okStatusList), gb, perc))
    toPrint = ["%s  %.2f MB/s" % (l, r) for l, r, in zip(data.okStatusList,
                                                         data.okRatesList)]
    myprint(toPrint, m)
    
    gb = data.notOkBytes / 1024.0 / 1024.0 / 1024.0
    perc = len(data.notOkStatusList) / (len(logFiles) / 100.0)
    m = ("'Exit Status: Not OK' files: %s files, %s GB in total, "
         "%s %%, log files:" % (len(data.notOkStatusList), gb, perc))
    myprint(data.notOkStatusList, m)
    
    inputData = (("Log files containing 'Exit Status: OK' where "
                  "TotalBytes and TotalNetworkBytes doesn't match, "
                  "%s files:\n", data.okNotMatchingBytes),
                 ("Log files containing neither 'Exit Status: OK' nor "
                  "'Exit Status: Not OK', %s files:\n", notOkNorNotOk),
                 ("Log files not containing 'Logger closing' at the "
                  "end (unclosed), %s files:\n", notClosed),
                 ("Log files containing 'AlreadyBeingCreated': %s files:\n",
                  data.alreadyBeingCreated),
                 ("Log files containing 'Attempt to log into already "
                  "closed': %s files:\n", data.loggerClosedList),
                 ("Log files containing 'Exit Status: Not OK' and not "
                  "'AlreadyBeingCreated' exception: %s files:\n",
                  notOkAndAlreadyBeingCreated),
                 ("Log files containing 'Address already in use': %s "
                  "files:\n", data.addressUsedList),
                 ("Log files not containing 'End of request "
                  "CleanupProcessesAction serving.': %s files:\n",
                  data.noEndingCleanupList)
                )
    
    for msg, d in inputData:
        m = msg % len(d)
        myprint(d, m)
        

if __name__ == "__main__":
    main()
