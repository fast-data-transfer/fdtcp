"""
py.test unittest testsuite for common.actions

__author__ = Zdenek Maxa

"""


import os
import sys
import signal
import tempfile
import inspect
import logging

import py.test
from mock import Mock

from fdtcplib.fdtd import FDTD
from fdtcplib.fdtd import ConfigFDTD
from fdtcplib.fdtcp import ConfigFDTCopy
from fdtcplib.utils.utils import getHostName, getDateTime, getRandomString
from fdtcplib.utils.Executor import Executor
from fdtcplib.utils.Logger import Logger

from fdtcplib.common.errors import FDTDException
from fdtcplib.common.actions import TestAction, ReceivingServerAction
from fdtcplib.common.actions import CleanupProcessesAction 
from fdtcplib.common.actions import SendingClientAction, Result
from fdtcplib.common.actions import CarrierBase, Action  
from fdtcplib.common.actions import TestAction, AuthServiceAction
from fdtcplib.common.actions import AuthClientAction



def getTempFile(content):
    f = tempfile.NamedTemporaryFile("w+") # read / write
    f.write(content)
    f.flush()
    f.seek(0)
    return f
    
    
def testTestActionId():
    t = TestAction("src", "dest", timeout = 4)
    assert t.timeout == 4
    
        
def testCarrierBase():
    cb = CarrierBase("some_id")
    assert cb.id == "some_id"
    
    
def testAction():
    a = Action("aa", 5)
    assert a.id == "aa"
    assert a.timeout == 5
    py.test.raises(NotImplementedError, a.execute)
    
    
def testTestAction():
    ta = TestAction("src", "dest", 5)
    assert ta.timeout == 5
    r = ta.execute()
    assert r.status == 0
    assert r.id == ta.id
    
    
def testReceivingServerAction():
    c = \
"""
[general]
fdtSendingClientCommand = sudo -u %(sudouser)s bash wrapper_fdt.sh -P 35 -p %(port)s -c %(hostDest)s -d / -fl %(fileList)s -noupdates
fdtReceivingServerCommand = sudo -u %(sudouser)s bash wrapper_fdt.sh -bs 2M -p %(port)s -noupdates
"""
    f = getTempFile(c)
    inputOption = "--config=%s" % f.name
    conf = ConfigFDTD(inputOption.split())
    a = ReceivingServerAction("some_id", dict(port=1000,
                              gridUserDest="someuser"))    
    a._setUp(conf, 1000)
    assert a.options["port"] == 1000
    # this one did not get interpolated for server action, so it's not set
    py.test.raises(KeyError, a.options.__getitem__,
                   "fdtSendingClientCommand")
    cmd = "sudo -u someuser bash wrapper_fdt.sh -bs 2M -p 1000 -noupdates"
    assert a.command == cmd

        
def testAuthServiceAction():
    c = \
"""
[general]
portAuthService = 9001
"""
    f = getTempFile(c)
    inputOption = "--config=%s" % f.name
    conf = ConfigFDTD(inputOption.split())
    a = AuthServiceAction("some_id")
    result = a.execute(conf=conf, logger=Mock())
    assert a.id == "some_id"
    assert result.serverPort == "9001"


def testAuthClientAction():
    c = \
"""
[general]
authClientCommand = bash authenticator/wrapper_auth.sh -p %(port)s -h %(host)s -u %(fileNameToStoreRemoteUserName)s
"""
    f = getTempFile(c)
    inputOption = "--config=%s host1:/tmp/file host2:/tmp/file1" % f.name
    conf = ConfigFDTCopy(inputOption.split())
    a = AuthClientAction("some_id", dict(port="someport",
                                         host="somehost"))
    fileNameToStoreRemoteUserName = ("/tmp/" + a.id + "--" +
                                     getRandomString('a', 'z', 5))
    a._setUp(conf, fileNameToStoreRemoteUserName)
    assert a.options["port"] == "someport"
    c = ("bash authenticator/wrapper_auth.sh -p someport -h somehost "
         "-u %s" % fileNameToStoreRemoteUserName)
    assert a.command == c

    
def testSendingClientAction():
    c = \
"""
[general]
fdtSendingClientCommand = bash wrapper_fdt.sh -P 35 -p %(port)s -c %(hostDest)s -d / -fl %(fileList)s -noupdates
fdtReceivingServerCommand = bash wrapper_fdt.sh -bs 2M -p %(port)s -noupdates
"""
    f = getTempFile(c)
    inputOption = "--config=%s" % f.name
    conf = ConfigFDTD(inputOption.split())
    options = dict(port="some_port", hostDest="host_dest",
                   transferFiles=[])        
    a = SendingClientAction("some_id", options)
    a._setUp(conf)
    assert a.options["fileList"] == "/tmp/fileLists/fdt-fileList-some_id"
    # this one did not get interpolated for client action, so it's not set
    py.test.raises(KeyError, a.options.__getitem__,
                   "fdtReceivingServerCommand")
    assert a.command == "bash wrapper_fdt.sh -P 35 -p some_port -c host_dest -d / -fl /tmp/fileLists/fdt-fileList-some_id -noupdates"
    # clean up after test, only if succeeded
    os.unlink(a.options["fileList"])
    
    
def testCleanupProcessesAction():
    logger = Logger()
    a = CleanupProcessesAction("some_id", timeout=4)
    assert a.id == "some_id"
    assert a.timeout == 4
    assert a.waitTimeout == True
    fdtd = Mock()
    # wihtout this, it remains in the loop, see
    # CleanupProcessesAction.execute() 
    fdtd.getExecutor().syncFlag = False
    r = a.execute(caller=fdtd, logger=logger)
    assert r.status == 0
    a = CleanupProcessesAction("some_id", timeout=5, waitTimeout=False)
    assert a.waitTimeout == False


def testResult():
    r = Result("some_id")
    str(r)
    assert r.id == "some_id"
    assert r.host == getHostName()
    
    
def testReceivingServerActionCheckTargetFileNames():
    logger = Logger()
    files = ["/mnt/data", "/etc/passwd", "/etc/something/nonsence", "/tmp"]
    options = dict(port = 1000, gridUserDest="someuser", destFiles=files)
    a = ReceivingServerAction("some_id", options)
    logger.info("%s - checking presence of files at target location ..." %
                a.__class__.__name__)
    r = a._checkTargetFileNames(files)
    logger.debug("Results:\n%s" % r)
    expected = \
"""    exists  True: /mnt/data
    exists False: /mnt/.data
    exists  True: /etc/passwd
    exists False: /etc/.passwd
    exists False: /etc/something/nonsence
    exists False: /etc/something/.nonsence
    exists  True: /tmp
    exists False: /.tmp
"""    
    assert r == expected
    

def testReceivingServerAddressAlreadyInUse():
    c = """
[general]
port = 6700
debug = DEBUG
portRangeFDTServer = 54321,54323
fdtReceivingServerCommand = java -jar ../fdtjava/fdt.jar -bs 64K -p %(port)s -wCount 5 -S -noupdates
fdtServerLogOutputTimeout = 2
fdtServerLogOutputToWaitFor = "FDTServer start listening on port: %(port)s"
fdtReceivingServerKillTimeout = 1
killCommand = "kill -9 %(pid)s"
killCommandSudo = "kill -9 %(pid)s"

"""
    f = getTempFile(c)
    inputOptions = "-d DEBUG -p 6700 --config=%s" % f.name
    conf = ConfigFDTD(inputOptions.split())
    testName =  inspect.stack()[0][3]
    logger = Logger(name = testName,  level = logging.DEBUG)
    apMon = None
    daemon = FDTD(conf, apMon, logger)        
    assert len(daemon._executors) == 0
    
    files = ["/mnt/data", "/etc/passwd", "/etc/something/nonsence", "/tmp"]
    options = dict(gridUserDest="someuser", destFiles=files)
    a = ReceivingServerAction("some_id", options)
    a._checkForAddressAlreadyInUseError("some message", 222, logger)
    a._checkForAddressAlreadyInUseError("some message", 25, logger)
    a._checkForAddressAlreadyInUseError("Address already in use", 25, logger)
    a._checkForAddressAlreadyInUseError("Address already in use", 22225,
                                        logger)
    
    logger.info("Now real FDT Java server real attempts")
    logger.info('#' * 78)
    
    # 1) successful attempt    
    logger.info('1' * 78)
    options = dict(gridUserDest="someuser", destFiles=files)
    a = ReceivingServerAction("some_id", options)    
    assert len(daemon._executors) == 0
    result = a.execute(conf=conf, caller=daemon, apMon=apMon, logger=logger)
    assert len(daemon._executors) == 1
    assert result.status == 0
    assert result.serverPort == 54321
    assert result.msg == "FDT server is running"
    
    # 2) this executor attempt shall fail with Address already in use,
    # fool into reusing the same port 54321 as the previous process
    # by replacing caller.getFreePort() method which is used in
    # ReceivingServerAction.exectute()
    def myFoolGetFreePort(inp, logger):
        def returner():
            logger.debug("myFoolGetFreePort called, returning %s" % inp)
            return inp
        return returner
    
    daemon.getFreePort = myFoolGetFreePort(54321, logger) 
    logger.info('2' * 78)
    options = dict(gridUserDest="someuser", destFiles=files)
    a = ReceivingServerAction("some_id-2", options)
    py.test.raises(FDTDException, a.execute, conf=conf, caller=daemon,
                   apMon=apMon, logger=logger)
    # starting FDT Java command failed, but the request remains in the
    # executor container for later cleanup
    assert len(daemon._executors) == 2
    
    # 3) kill both executors / processes - one running, other failed
    logger.info('3' * 78)
    daemon.killProcess("some_id", logger, waitTimeout = False)
    assert len(daemon._executors) == 1
    daemon.killProcess("some_id-2", logger, waitTimeout = False)
    assert len(daemon._executors) == 0
    
    # 4) try starting FDT Java server on privileged port - will fail
    logger.info('4' * 78)
    options = dict(gridUserDest="someuser", destFiles=files)
    a = ReceivingServerAction("some_id", options)
    daemon.getFreePort = myFoolGetFreePort(999, logger)
    py.test.raises(FDTDException, a.execute, conf=conf, caller=daemon,
                   apMon=apMon, logger=logger)
    assert len(daemon._executors) == 1
    daemon.killProcess("some_id", logger, waitTimeout=False)
    assert len(daemon._executors) == 0
    
    daemon.shutdown()
    daemon.pyroDaemon.closedown()
