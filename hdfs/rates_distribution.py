#!/usr/bin/env python

"""
Script to plot distibution of transfers rates.

rates is a part of the fdtd-log_analyzer.py script with the successful
transfers.
Rate is calculated as division of the total transferred MB as reported
by FDT Java and time delta of the first and very last log message in the
transfer log file.

"""
    

import sys
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

NUM_BINS = 30


class PlotData(object):
    def __init__(self):
        self.rateBins = [] # x axis
        # what will be plotted - number of occurrences in the time bin
        self.y = [] 
        
        
# load the data
ratesList = []
try:
    inputFile = sys.argv[1]
except IndexError:
    print "requires input argument - input file"
    sys.exit(1)
    
fd = open(inputFile, 'r')
for line in fd:
    # expects line in following format:
    # transfer-fdtcp-cithep249.ultralight.org--srm.unl.edu-to-gridftp05.ultralight.org--2011-04-24-01h:09m:42s-bqtsq.log  21.13 MB/s
    rate = line.split()[1]
    rate = float(rate)
    ratesList.append(rate)
fd.close()

print "%s input values" % len(ratesList)

pd = PlotData()
    
# create bins based on min, resp. max. value of rate values to plot
ma = max(ratesList)
mi = min(ratesList)
print "min value: %s max value: %s" % (mi, ma)
binSize = (ma - mi) / float(NUM_BINS)
currBin = mi
c = 0
while currBin < ma:
    currBin = mi + c * binSize
    pd.rateBins.append(currBin)
    pd.y.append(0)
    c += 1
    
for rate in ratesList:
    diff = float('inf')
    for i in range(len(pd.rateBins)):
        currDiff = abs(pd.rateBins[i] - rate)
        if currDiff < diff:
            indToBin = i
            diff = currDiff
    pd.y[indToBin] += 1
        

# sanity check
numBinned = 0
for binned in pd.y:
    numBinned += binned
    
print "total number of binned values: %s (must be the same as number of input values)" % numBinned


# process result lists - consider only those which has occurrence > 0
toPlotX = []
toPlotY = []
for i in range(len(pd.y)):
    if pd.y[i] > 0:
        toPlotX.append(pd.rateBins[i])
        toPlotY.append(pd.y[i])

print "###### to plot:"
print toPlotX
print toPlotY

pylab.setp(pylab.gca().get_xticklabels(), rotation=45, horizontalalignment='right')
pylab.plot(toPlotX, toPlotY, 'rs')

pylab.xlabel("transfer rate bins of size %.2f MB/s" % binSize)
pylab.ylabel("number of occurrences of the rate")
pylab.title("Transfer performance distribution over %s measurements" % len(ratesList))
pylab.grid(True)

# saves plot into a png file
#pylab.savefig('simple_plot')

#pylab.subplots_adjust(left=0.3, bottom=0.3)
#ggpylab.subplots_adjust(bottom=0.18)

pylab.show()
