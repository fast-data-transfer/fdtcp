#!/usr/bin/env python

"""

Script for plot on occurrence study of
"AlreadyBeingCreatedException" in Hadoop DFS.
#40 https://trac.hep.caltech.edu/trac/fdtcp/ticket/40
#39 https://trac.hep.caltech.edu/trac/fdtcp/ticket/39 (parent ticket)

AlreadyBeingCreated-log_file_names - list of transfer separate log file
    names when this exception occurred (61 cases during 
    2011-04-12--06h:43m to 2011-04-14--10h:46m (~52h))
    details on #5:comment:20
AlreadyBeingCreated-timestamps - just timestamps extracted
    the timestamps are times of when the transfer was initiated
    on the fdtcp side, not exactly time when the exception occurred but
    for occurrence dependency study it should be approximately enough.

"""
    

import time
import sys
import datetime
import numpy
import pylab
from matplotlib.dates import date2num
import matplotlib as mpl

"""
help
a = [10, 20, 22, 24, 25]
b = [1.2, 1, 0.9, 1.3, 1.9]
pylab.plot(a) # generates default x data
pylab.plot(b)
pylab.plot(a, b, 'rs', a, b, 'k')
"""

BIN_SIZE = 4
# max. pause during which the exception didn't occur was over 5h, so
# make the entire period 6h (360mins)
ENTIRE_PERIOD = 360  


class PlotData(object):
    """
    PlotData - time bins are BIN_SIZE minutes bins into which fall
    exception events offsets from the previous occurrence.
     
    """
    def __init__(self):
        self.timeBins = []
        self.x = [] # what will be plotted - number of minutes bins on X axis
        self.y = [] # what will be plotted - number of occurrences in the time bin
        
        

# make bins of BIN_SIZE up ENTIRE_PERIOD
pd = PlotData()
for i in range(BIN_SIZE, ENTIRE_PERIOD, BIN_SIZE):
    hour = i / 60
    min = i - (hour * 60)
    t = datetime.time(hour, min)
    pd.timeBins.append(t)
    pd.x.append(i)
    pd.y.append(0)


# reference time for calculating time delta, time difference
refDelta = datetime.time(0, BIN_SIZE)
datetimes = [] # on x axis
for dt in open("AlreadyBeingCreated-timestamps", 'r'):
    dt = dt.strip()
    dt = dt.split('-')
    dt = [int(c) for c in dt]
    dObj = datetime.datetime(*dt)

    delta = None
    # can only calculate delta in the second iteration
    if len(datetimes) != 0:
        delta = dObj - previous
    
    previous = dObj

    datetimes.append(date2num(dObj))

    # can't do anything on the first iteration
    if not delta:
        continue

    # delta is in form 0:18:51.515249
    sDelta = str(delta).split(':')
    iDelta = [int(c) for c in (sDelta[0], sDelta[1])]
    deltaMin = (60 * iDelta[0]) + iDelta[1]
    for i in range(len(pd.timeBins)):
        calc = abs(deltaMin - pd.x[i])
        # "deltaMin in range(4/2)" makes the first bin since the subtraction
        # will still be larger than the half size of the bin ...
        if calc <= BIN_SIZE / 2 or deltaMin in range(BIN_SIZE / 2):
            pd.y[i] += 1
            #print ("%s falls into %s (occup:%s)" % (delta, pd.x[i], pd.y[i]))
            break
    else:
        print "not binned: %s %s" % (delta, deltaMin)

print pd.y
t = 0
for c in pd.y:
    t += c
print ("number of total occurrences: %s (must be the same as number of "
       "lines in the input file - 1)" % t)

# process result lists - consider only those which has occurrence > 0
toPlotX = []
toPlotY = []
for i in range(len(pd.y)):
    if pd.y[i] > 0:
        toPlotX.append(pd.x[i])
        toPlotY.append(pd.y[i])

print "###### to plot:"
print toPlotX
print toPlotY

pylab.setp(pylab.gca().get_xticklabels(), rotation=45, horizontalalignment='right')
pylab.plot(toPlotX, toPlotY, 'rs')

pylab.xlabel("%s [min] time offset bins (time from previous occurrence)" % BIN_SIZE)
pylab.ylabel("number of occurrences with corresponding time offset")
pylab.title("AlreadyBeingCreated HDFS exceptions time offset occurrences")
pylab.grid(True)

# saves plot into a png file
#pylab.savefig('simple_plot')

#pylab.subplots_adjust(left=0.3, bottom=0.3)
#ggpylab.subplots_adjust(bottom=0.18)

pylab.show()
