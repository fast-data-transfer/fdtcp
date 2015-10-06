"""
Generate data files used in transfer tests.

"""

import os

# number of files to generate
numFiles = 100
sizeGB = 1 # GB


# ---------------------------------------------------------------------------

# size of files to generate (in bytes)
# 1024 * 1024 * 1024 = 1GB ; 1048576 = 1024 * 1024
# 1024 * 1024 * 100 = 100MB
size = 1024 * 1024 * 1024 * sizeGB # sizeGB GB

# ---------------------------------------------------------------------------

_blockSize = 1024
_count = size / _blockSize

_command = "dd if=/dev/zero of=./%(sizeGB)sGB-%(counter)s.test bs=%(blockSize)s count=%(count)s"

_commands = [_command % {"sizeGB": sizeGB, "counter": "%.2i" % (i + 1), 
             "blockSize": _blockSize, "count": _count} for i in range(numFiles)]


#print "commands:\n", _commands

for comm in _commands:
    print "executing command: %s" % comm
    r = os.system(comm)
    print "result: %s\n" % r
