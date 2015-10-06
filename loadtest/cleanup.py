"""
cleanup.py

* deletes directory structure at the destination
* deletes temporary files
* re-creates desired directory structure at the destination for running
*   the loadtest

* run at the destination (usually T2) as
    cd loadtest
    sudo -u uscms1713 python cleanup.py
"""

DEST = "/mnt/hadoop/store/user/maxa/fdtcptests/"
FILES = "/tmp/fdt*"
# number of tests are iterated from 1
NUMTESTS = 10


import os, shutil

c = "rm -fr %s" % FILES
print "cleaning files: %s" % c
os.system(c)

if os.path.exists(DEST):
    print "deleting directory tree: %s" % DEST
    shutil.rmtree(DEST)
    os.mkdir(DEST)
    
    # not necessary - the permissions are right, FDT will create
    # non-existing destination directories itself
    #print "creating loadtest directory structure ..."
    ## number of tests are iterated from 1
    #for i in range(1, NUMTESTS + 1):
    #    dirName = "test-%03d" % i
    #    path = os.path.join(DEST, dirName)
    #    os.mkdir(path)
    #os.system("ls -R %s" % DEST)
else:
    print "directory '%s', nothing done" % DEST 
