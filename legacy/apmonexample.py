# example for testing / setting up ApMon MonALISA monitoring

from ApMon import apmon
import time
import random

# read destination hosts from file
#apm = apmon.ApMon("http://monalisa2.cern.ch/~catac/apmon/destinations.conf");

# set the destinations as a tuple of strings
apm = apmon.ApMon(("monalisa2.cern.ch:28884", "monalisa2.caltech.edu:28884"))

#check for changes in the configuration files
#apm.configRecheck = True
#apm.configRecheckInterval = 10 # (time in seconds)

print "ApmTest: Destinations:", apm.destinations

# what happens if hostname is not specified? - puts just 'localhost'


transferId = "some_id"

print "sending stuff ..."

for i in range(20):
    par = dict(id = transferId, initialisation = random.randint(10, 30))
    apm.sendParameters("fdtcp", None, par)
    time.sleep(0.05)
    
    
for i in range(20):
    par = dict(id = transferId, transfer_time = random.randint(10, 30))
    apm.sendParameters("fdtcp", None, par)
    time.sleep(0.05)
    
print "fdtcp stuff sent"

for i in range(20):
    par = dict(id = transferId, fdt_server_init = random.randint(10, 30))
    apm.sendParameters("fdtd_server_writer", None, par)
    time.sleep(0.05)
    
print "fdtd_server_writer stuff sent"


print "ApmTest: Done."
apm.free()    


# ---------------------------------------------------------------------------
# following is ApMon example

# nodeName will be the machine's full hostname
#apm.sendParameters("MyCluster1_py", None, {'a': .5, 'b': 23, 'c': 3.32, 'd':4.99})
#apm.sendParameters("MyCluster1_py_in_order", None, [('a', .5), ('b', 23), ('c', 3.32), ('d', 4.99)])
#
## clusterName will be "MyCluster1", given by last sendParameters call.
#apm.sendParameter(None, "MyNodeName", "jobs_started", 10)
#
## default clusterName will be changed
#apm.sendParameter("MyCluster2_py", "MyNodeName", "total_memory", 20)
#
#for i in range (50):
#    # clusterName = "MyCluster2", given by last apmon call
#    # nodeName = the machine's full hostname
#    apm.sendParams ({'cpu_load': ((i % 11)/10.0), 'jobs_finished': i })
#    print "ApmTest: sent",((i % 11)/10.0), i%11
#    time.sleep (.005)