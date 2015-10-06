"""
py.test unittest testsuite for ConfigFDTCopy.

__author__ = Zdenek Maxa

"""


import os
import sys
import logging
import tempfile

import py.test
from mock import Mock

from fdtcplib.fdtd import ConfigFDTD
from fdtcplib.utils.Config import Config, ConfigurationException



def getTempFile(content):
    f = tempfile.NamedTemporaryFile("w+") # read / write
    f.write(content)
    f.flush()
    f.seek(0)
    return f
    

def testConfigFDTDValuesPresence():
    c = """
[general]
# some mandatory options missing
val1 = 9000
val2 = 9000    
"""
    f = getTempFile(c)
    inputOption = "--config=%s" % f.name
    conf = ConfigFDTD(inputOption.split())
    py.test.raises(ConfigurationException, conf.sanitize)


def testConfigFDTDCorrectValues():
    c = \
"""
[general]
port = 9000
fdtSendingClientCommand = cmd1
fdtReceivingServerCommand = cmd2
portAuthService = 9001
daemonize = False
pidFile = /tmp/something.log
portRangeFDTServer = 54321,54400
transferSeparateLogFile = True
debug = INFO
fdtSendingClientKillTimeout = 10
fdtServerLogOutputTimeout = 11
fdtReceivingServerKillTimeout = 12
authServiceLogOutputTimeout = 13
fdtServerLogOutputToWaitFor = somelog
authServiceLogOutputToWaitFor = someotherlog
# strings - both with " and without " shall work identically 
authServiceCommand = "authcommand"
killCommandSudo = "kill command sudo"
killCommand = "kill command"
"""

    f = getTempFile(c)
    inputOption = "--config=%s" % f.name
    conf = ConfigFDTD(inputOption.split())
    conf.sanitize()
    
    f = getTempFile(c)
    inputOption = "-d DEBUG -p 6700 --config=%s" % f.name
    conf = ConfigFDTD(inputOption.split())
    conf.sanitize()
    assert conf.get("debug") == logging.DEBUG
    assert conf.get("port") == 6700
    assert conf.get("fdtSendingClientCommand") == "cmd1"
    assert conf.get("fdtReceivingServerCommand") == "cmd2"  
    assert conf.get("nonsenceoption") == None
    # processing happens on this stage
    assert conf.get("portRangeFDTServer") == "54321,54400"
    assert conf.get("transferSeparateLogFile") == True
    assert conf.get("fdtSendingClientKillTimeout") == 10
    assert conf.get("fdtServerLogOutputTimeout") == 11
    assert conf.get("fdtReceivingServerKillTimeout") == 12
    assert conf.get("authServiceLogOutputTimeout") == 13
    assert conf.get("fdtServerLogOutputToWaitFor") == "somelog"
    assert conf.get("authServiceLogOutputToWaitFor") == "someotherlog"
    assert conf.get("authServiceCommand") == "authcommand"
    assert conf.get("killCommandSudo") == "kill command sudo"
    assert conf.get("killCommand") == "kill command"
    assert conf.get("daemonize") == False
    assert conf.get("pidFile") == "/tmp/something.log"
    
    
    
def testConfigFDTDValuesPresentButInvalid():
    confs = [ \
"""
[general]
port = 9000x
fdtSendingClientCommand = None # can't test at this stage
fdtReceivingServerCommand = None # can't test at this stage
debug = DEBUG
""",             
"""
[general]
port = 9000
fdtSendingClientCommand = None # can't test at this stage
fdtReceivingServerCommand = None # can't test at this stage
debug = DEBU
"""]
    
    for c in confs:
        f = getTempFile(c)
        inputOption = "--config=%s" % f.name
        conf = ConfigFDTD(inputOption.split())
        print "testing config: '%s'" % c
        py.test.raises(ConfigurationException, conf.sanitize)
