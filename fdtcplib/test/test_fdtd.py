"""
py.test unittest testsuite for fdtd

daemon.pyroDaemon.closedown() call removed from FDTD.shutdown() since it was
troublesome and sometimes the daemon was hanging on it preventing completion
of the shutdown sequence. However, if necessary or handy to bind the same
port number in quick consecutive order, this call seems to be necessary,
otherwise the next pyro daemon initialization gives always 'address already
in use' error.

__author__ = Zdenek Maxa

"""


import os
import sys
import tempfile
import signal
import logging
import time
import tempfile
import inspect

import psutil
from psutil import Process, NoSuchProcess
import py.test
from mock import Mock

from fdtcplib.fdtd import FDTD
from fdtcplib.fdtd import daemonize
from fdtcplib.fdtd import FDTDService
from fdtcplib.fdtd import ConfigFDTD
from fdtcplib.fdtd import AuthService
from fdtcplib.fdtd import PortReservation
from fdtcplib.common.errors import FDTDException, AuthServiceException
from fdtcplib.common.errors import PortReservationException
from fdtcplib.utils.utils import getUserName
from fdtcplib.utils.Logger import Logger
from fdtcplib.utils.Executor import Executor
from fdtcplib.utils.utils import getOpenFilesList
from fdtcplib.common.TransferFile import TransferFile
from fdtcplib.common.actions import TestAction, ReceivingServerAction
from fdtcplib.common.actions import SendingClientAction
from fdtcplib.common.actions import CleanupProcessesAction
from fdtcplib.utils.Config import ConfigurationException
from fdtcplib.utils.utils import getOpenFilesList



def getTempFile(content):
    f = tempfile.NamedTemporaryFile("w+") # read / write
    f.write(content)
    f.flush()
    f.seek(0)
    return f


def testConfigIllegalPort():
    # wrong port - expect exception - port as string
    inputOptions = "-d DEBUG -p ABC"
    testName =  inspect.stack()[0][3]  
    logger = Logger(name=testName,  level=logging.DEBUG)
    conf = ConfigFDTD(inputOptions.split())
    apMon = None
    py.test.raises(FDTDException, FDTD, conf, apMon, logger)
    
    # if port is not set ...
    conf._options["port"] = None
    apMon = None
    py.test.raises(FDTDException, FDTD, conf, apMon, logger)
    

def testFDTDAndExecutorContainerHandling():
    c = """
[general]
port = 6700
debug = DEBUG
portRangeFDTServer = 54321,54323
killCommand = "kill -9 %(pid)s"
killCommandSudo = "kill -9 %(pid)s"
"""
    f = getTempFile(c)
    inputOptions = "-d DEBUG -p 6700 --config=%s" % f.name
    conf = ConfigFDTD(inputOptions.split())
    testName =  inspect.stack()[0][3]
    logger = Logger(name=testName,  level=logging.DEBUG)
    apMon = None
    daemon = FDTD(conf, apMon, logger)        
    assert len(daemon._executors) == 0
    # needs to be blocking command, since simple ls finishes too quickly
    # for default blocking it would be considered that it failed
    # just needed existing process and executor container handling with it
    executor = Executor("some_id", "ls /tmp", logger=logger, blocking=True)
    executor.execute()
    daemon.addExecutor(executor)
    # subsequent adding of the same executor shall raise exception
    # (the same id)
    py.test.raises(FDTDException, daemon.addExecutor, executor)
    daemon.removeExecutor(executor)
    assert len(daemon._executors) == 0

    # need long running job
    command = "dd if=/dev/zero of=/dev/null count=100000000 bs=102400"
    # caller is not explicitly specified, so all executors container
    # manipulation is done from this test
    executor = Executor("some_id",
                        command,
                        blocking=False,
                        killTimeout=0,
                        logger=logger)
    executor.execute()
    daemon.addExecutor(executor)
    assert len(daemon._executors) == 1
    
    # check getting the executor reference from the container 
    ex = daemon.getExecutor("some_id_nonsence") # doens't exist
    assert ex == None
    ex = daemon.getExecutor("some_id")
    assert ex == executor

    # this in fact should discover that the process is still running
    # and not remove it
    daemon.removeExecutor(executor)
    assert len(daemon._executors) == 1
    # now kill the process and try to remove it afterwards - test
    # different branch of removeExecutor
    daemon.killProcess(executor.id, logger)
    assert len(daemon._executors) == 0 # should have been removed
    
    daemon.shutdown()
    daemon.pyroDaemon.closedown()
    

def testFDTDDesiredPortOccupiedRaisesException():
    inputOptions = "-d DEBUG -p 6700 -H localhost"
    conf = ConfigFDTD(inputOptions.split())
    testName =  inspect.stack()[0][3]
    logger = Logger(name=testName, level=logging.DEBUG)
    apMon = None
    daemon = FDTD(conf, apMon, logger)
    py.test.raises(FDTDException, FDTD, conf, apMon, logger)    
    daemon.shutdown()
    daemon.pyroDaemon.closedown()
        

def testFDTDKillProcess1():
    inputOptions = "-d DEBUG -p 6700 -H localhost"
    conf = ConfigFDTD(inputOptions.split())
    testName =  inspect.stack()[0][3]
    logger = Logger(name=testName, level=logging.DEBUG)
    apMon = None
    daemon = FDTD(conf, apMon, logger)
    # now doesn't fail, just says "some_id" process doesn't exist in the
    # executors container
    daemon.killProcess("some_id", logger)
    daemon.shutdown()
    daemon.pyroDaemon.closedown()
        

def testFDTDKillProcess2():
    c = """
[general]
port = 6700
debug = DEBUG
killCommand = ../wrapper_kill.sh %(pid)s
portRangeFDTServer = 54321,54400
"""
    f = getTempFile(c)
    inputOption = "--config=%s" % f.name
    conf = ConfigFDTD(inputOption.split())
    testName =  inspect.stack()[0][3]
    logger = Logger(name=testName, level=logging.DEBUG)
    apMon = None
    daemon = FDTD(conf, apMon, logger)
    
    # need long-running, non blocking process
    command = "dd if=/dev/zero of=/dev/null count=100000000 bs=102400"    
    executor = Executor("some_id",
                        command,
                        blocking=False,
                        caller=daemon,
                        logger=logger,
                        killTimeout=0)
    try:
        executor.execute()
        daemon.killProcess("some_id", logger)
    finally:
        # definitely release port and kill the process
        daemon.shutdown()
        daemon.pyroDaemon.closedown()
        
    try:
        p = Process(executor.proc.pid)
        m = ("FAIL: Process PID:%s should have been "
             "killed." % executor.proc.pid) 
        logger.debug(m)
        py.test.fail(m)
    except NoSuchProcess, ex:
        logger.debug("OK: Process PID:%s doesn't exist now." %
                     executor.proc.pid)

                
def testAuthService():
    inputOptions = "-d DEBUG -p 6700 -H localhost"
    conf = ConfigFDTD(inputOptions.split())
    testName =  inspect.stack()[0][3]
    logger = Logger(name=testName, level=logging.DEBUG)
    apMon = None
    daemon = FDTD(conf, apMon, logger)
    # shall fail due to unavailable grid credentials (when running locally)
    py.test.raises(AuthServiceException, AuthService, daemon, conf, logger)
    daemon.shutdown()
    daemon.pyroDaemon.closedown()
    
    
def testCorrectPortRange():
    c = """
[general]
port = 5000
portRangeFDTServer = 54321,54400
"""
    f = getTempFile(c)
    inputOption = "--config=%s" % f.name
    conf = ConfigFDTD(inputOption.split())
    testName =  inspect.stack()[0][3]
    logger = Logger(name=testName, level=logging.DEBUG)
    apMon = None
    daemon = FDTD(conf, apMon, logger)
    assert daemon._portMgmt._ports[0]._port == 54321
    assert daemon._portMgmt._ports[-1]._port == 54400 
    daemon.shutdown()
    daemon.pyroDaemon.closedown()


def testWrongPortRange():
    c = """
[general]
port = 5000
portRangeFDTServer = 54321,54400x
"""
    f = getTempFile(c)
    inputOption = "--config=%s" % f.name
    conf = ConfigFDTD(inputOption.split())
    testName =  inspect.stack()[0][3]
    logger = Logger(name=testName, level=logging.DEBUG)
    apMon = None
    py.test.raises(FDTDException, FDTD, conf, apMon, logger)
    
    c = """
[general]
port = 5000
portRangeFDTServer = 54321:54400
"""
    f = getTempFile(c)
    inputOption = "--config=%s" % f.name
    conf = ConfigFDTD(inputOption.split())
    testName =  inspect.stack()[0][3]
    logger = Logger(name=testName, level=logging.DEBUG)
    apMon = None
    py.test.raises(FDTDException, FDTD, conf, apMon, logger)


def testGetFreePort():
    c = """
[general]
port = 5000
portRangeFDTServer = 54321,54323
"""
    f = getTempFile(c)
    inputOption = "--config=%s" % f.name
    conf = ConfigFDTD(inputOption.split())
    testName =  inspect.stack()[0][3]
    logger = Logger(name=testName, level=logging.DEBUG)
    apMon = None
    daemon = FDTD(conf, apMon, logger)
    assert daemon.getFreePort() == 54321
    assert daemon.getFreePort() == 54322
    assert daemon.getFreePort() == 54323
    py.test.raises(PortReservationException, daemon.getFreePort)    
    daemon.shutdown()
    daemon.pyroDaemon.closedown()
    
    
def testReleasePort():
    c = """
[general]
port = 5000
portRangeFDTServer = 54321,54323
"""    
    # only ports 54321, 54322, 54323 are available to play:
    f = getTempFile(c)
    inputOption = "--config=%s" % f.name
    conf = ConfigFDTD(inputOption.split())
    testName =  inspect.stack()[0][3]
    logger = Logger(name=testName, level=logging.DEBUG)
    apMon = None
    daemon = FDTD(conf, apMon, logger)
    assert daemon.getFreePort() == 54321
    assert daemon.getFreePort() == 54322
    # nothing should happen
    py.test.raises(PortReservationException, daemon.releasePort, 20) 
    py.test.raises(PortReservationException, daemon.releasePort, "aa")
    assert daemon.getFreePort() == 54323
    
    daemon.releasePort(54321) 
    daemon.releasePort(54322)
    
    assert daemon.getFreePort() == 54321
    assert daemon.getFreePort() == 54322
    py.test.raises(PortReservationException, daemon.getFreePort)
    
    daemon.shutdown()
    daemon.pyroDaemon.closedown()

    
def testKillProcessTimeout():
    c = """
[general]
port = 6700
debug = DEBUG
killCommand = ../wrapper_kill.sh %(pid)s
portRangeFDTServer = 54321,54400
"""
    
    script = """
c=$1
while [ $c -gt 0 ]
do
    sleep 1
    let "c -= 1"
done
exit 0
"""
    f = getTempFile(c)
    inputOption = "--config=%s" % f.name
    conf = ConfigFDTD(inputOption.split())
    testName =  inspect.stack()[0][3]
    logger = Logger(name=testName, level=logging.DEBUG)
    apMon = None
    daemon = FDTD(conf, apMon, logger)

    f = getTempFile(script)
    # wait time 5s
    command = "bash %s 5" % f.name
    
    # wait only 2s for me before killing
    e = Executor("some_id",
                 command,
                 caller=daemon,
                 blocking=False,
                 killTimeout=3,
                 logger=logger)    

    try:
        output = e.execute()
        daemon.killProcess("some_id", logger)
    finally:
        daemon.shutdown()
        daemon.pyroDaemon.closedown()
    
    # the process was still running, timeout elapsed and was killed
    assert e.proc.poll() == -9 
    
    # try different port, even if the previous was released,
    # immediate rebinding attempt makes PYRO fail
    inputOptions = "-d DEBUG -p 6701"
    conf = ConfigFDTD(inputOptions.split())
    apMon = None
    daemon = FDTD(conf, apMon, logger)

    # wait time 2s
    command = "bash %s 2" % f.name
    e = Executor("some_id",
                 command,
                 caller=daemon,
                 blocking=False,
                 killTimeout=4,
                 logger=logger)

    try:
        output = e.execute()
        daemon.killProcess("some_id", logger)
    finally:
        daemon.shutdown()
        daemon.pyroDaemon.closedown()        
    
    # the process should have normally finished, waiting killTimeout
    assert e.proc.poll() == 0
    
    
def testFDTDWaitingTimeoutWhenCleanup():
    """
    Test issues long running job (dd copy) on the background (non-blocking)
    and when killing the job, the timeout is set higher than issuing ALARM
    signal. It's tested that the ALARM signal was raised, but implemented
    as is is in fact ignored. More obvious when the killTimeout is set much
    higher.
    Implementation of #33 - CleanupProcessesAction - attribute to ignore any
         wait-to-finish timeouts    
    
    """ 
    class Handler:
        def __init__(self, flag, testName):
            self.flag = flag
            self.testName = testName
        def signalHandler(self, signum, frame):
            print("test %s signal handler called (sig: %s)" %
                  (self.testName, signum))
            # sets flag to check whether some reaction was successfully
            # invoked
            self.flag = True 

    c = """
[general]
port = 6700
debug = DEBUG
killCommand = ../wrapper_kill.sh %(pid)s
portRangeFDTServer = 54321,54400
"""
    f = getTempFile(c)
    inputOption = "--config=%s" % f.name
    conf = ConfigFDTD(inputOption.split())
    testName =  inspect.stack()[0][3]
    logger = Logger(name=testName, level=logging.DEBUG)
    apMon = None
    fdtd = FDTD(conf, apMon, logger)
    
    # need long running job
    command = "dd if=/dev/zero of=/dev/null count=100000000 bs=102400"
    # set long timeout (will be interrupted sooner by alarm - while
    # waiting on kill timeout)
    e = Executor("some_id",
                 command,
                 caller=fdtd,
                 blocking=False,
                 killTimeout=2,
                 logger=logger)
    try:
        e.execute() # command remains is running now
        # try killing the command
        # since waitTimeout = True, kill will be waiting    
        cl = CleanupProcessesAction("some_id", timeout=1, waitTimeout=True)
        handler = Handler(False, testName)
        signal.signal(signal.SIGALRM, handler.signalHandler)
        assert handler.flag == False
        print "test %s is waiting here ..." % testName
        signal.alarm(1) # raise alarm in timeout seconds
        cl.execute(conf=conf, caller=fdtd, apMon=None, logger=logger)
        signal.alarm(0) # disable alarm
        # but the alarm was called during this waiting (test flag value)
        assert handler.flag == True
    finally:
        fdtd.shutdown()
        fdtd.pyroDaemon.closedown()
        
        
def testFDTDNotWaitingTimeoutWhenCleanupForced():
    """
    Test issues long running job (dd copy) on the background (non-blocking)
    and when killing the job, the timeout is set high. But no timeout is
    waited and the command is killed immediately. Raising ALARM in 2s never
    happens and command shall finish immediately (value of the flag changed
    in the signal handler never happens).
    Implementation of #33 - CleanupProcessesAction - attribute to ignore any
         wait-to-finish timeouts
    
    """ 
    class Handler:
        def __init__(self, flag, testName):
            self.flag = flag
            self.testName = testName
        def signalHandler(self, signum, frame):
            print("test %s signal handler called (sig: %s)" %
                  (self.testName, signum))
            # sets flag to check whether some reaction was successfully
            # invoked
            self.flag = True

    c = """
[general]
port = 6700
debug = DEBUG
killCommand = ../wrapper_kill.sh %(pid)s
portRangeFDTServer = 54321,54400
"""
    f = getTempFile(c)
    inputOption = "--config=%s" % f.name
    conf = ConfigFDTD(inputOption.split())
    testName =  inspect.stack()[0][3]
    logger = Logger(name=testName, level=logging.DEBUG)
    apMon = None
    fdtd = FDTD(conf, apMon, logger)
    
    # need long running job
    command = "dd if=/dev/zero of=/dev/null count=100000000 bs=102400"
    # set long timeout, shall be killed immediately anyway
    e = Executor("some_id",
                 command,
                 caller=fdtd,
                 blocking=False,
                 killTimeout=100,
                 logger=logger)
    try:
        e.execute() # command remains is running now
        
        # try killing the command
        # since waitTimeout = False, shall be killed immediately    
        cl = CleanupProcessesAction("some_id", timeout=1, waitTimeout=False)
        handler = Handler(False, testName)
        signal.signal(signal.SIGALRM, handler.signalHandler)
        assert handler.flag == False
        signal.alarm(1) # raise alarm in timeout seconds
        # should happen immediately so that ALARM is not raised
        cl.execute(conf=conf, caller=fdtd, apMon=None, logger=logger)
        signal.alarm(0) # disable alarm
        # the alarm shouldn't have been called - value should have
        # remained the same
        assert handler.flag == False
    finally:
        fdtd.shutdown()
        fdtd.pyroDaemon.closedown()
      

functionalFDTDConfiguration = \
"""
[general]
port = 6700
debug = DEBUG
killCommand = ../wrapper_kill.sh %(pid)s
portRangeFDTServer = 54321,54400
transferSeparateLogFile = True # important for this test

# notice -notmp option which prevents from creating temp files (.file) which
# is useful e.g. when doing a dummy transfer /dev/zero -> /dev/null
# file fileFile (.null) could not be created
fdtSendingClientCommand = java -jar ../fdtjava/fdt.jar -P 16 -p %(port)s -c %(hostDest)s -d / -fl %(fileList)s -rCount 5 -notmp -noupdates
fdtSendingClientKillTimeout = 1
fdtReceivingServerCommand = java -jar ../fdtjava/fdt.jar -bs 64K -p %(port)s -wCount 5 -f %(clientIP)s -S -noupdates
fdtServerLogOutputTimeout = 2
fdtServerLogOutputToWaitFor = "FDTServer start listening on port: %(port)s"
fdtReceivingServerKillTimeout = 1
killCommand = "kill -9 %(pid)s"
killCommandSudo = "kill -9 %(pid)s"

# will not be used in this test, but are mandatory (when doing sanitize() on configuration)
# which is necessary since string "DEBUG" is in fact wrong, sanitize()     does the conversion
portAuthService = 0
authServiceLogOutputTimeout = 0
authServiceLogOutputToWaitFor = empty
authServiceCommand = "empty"
daemonize = 0
"""
        

def testFDTDServiceOpenFiles():
    """
    #41 - Too many open files (fdtd side)
    
    """
    hostName = os.uname()[1]
    f = getTempFile(functionalFDTDConfiguration)
    inputOption = "--config=%s" % f.name
    conf = ConfigFDTD(inputOption.split())
    conf.sanitize()
    testName =  inspect.stack()[0][3]
    logger = Logger(name=testName,
                    logFile="/tmp/fdtdtest-%s.log" % testName,
                    level=logging.DEBUG)
    apMon = None
    fdtd = FDTD(conf, apMon, logger)
    
    proc = Process(os.getpid())
    initStateNumOpenFiles = len(proc.get_open_files())
    
    for testAction in [TestAction("fakeSrc", "fakeDst") for i in range(3)]:
        r = fdtd.service.service(testAction)
        logger.debug("Result: %s" % r)
        assert r.status == 0
        
    # after TestAction, there should not be left behind any open files
    numOpenFilesNow = len(proc.get_open_files())
    assert initStateNumOpenFiles == numOpenFilesNow 
    
    # test on ReceivingServerAction - it's action after which the
    # separate logger is not closed, test the number of open files went +1,
    # send CleanupProcessesAction and shall again remain
    # initStateNumOpenFiles send appropriate TestAction first (like in real)
    serverId = "server-id"
    testAction  = TestAction(hostName, hostName)
    testAction.id = serverId 
    r = fdtd.service.service(testAction)
    assert r.status == 0
    options = dict(gridUserDest="someuserDest",
                   clientIP=os.uname()[1],
                   destFiles=[])    
    recvServerAction = ReceivingServerAction(testAction.id, options)
    r = fdtd.service.service(recvServerAction)
    print r.msg
    assert r.status == 0
    numOpenFilesNow = len(proc.get_open_files())
    # there should be only 1 extra opened file now
    assert initStateNumOpenFiles == numOpenFilesNow - 1
    cleanupAction = CleanupProcessesAction(serverId, timeout=2)
    r = fdtd.service.service(cleanupAction)
    print r.msg
    assert r.status == 0
    numOpenFilesNow = len(proc.get_open_files())
    assert initStateNumOpenFiles == numOpenFilesNow
    
    fdtd.shutdown()
    fdtd.pyroDaemon.closedown()
    logger.close()
    
    
def testAddressAlreadyInUseRoundRobinPortReservation():
    """
    #38 - Address already in use FDT Java
    https://trac.hep.caltech.edu/trac/fdtcp/ticket/38
    
    Address already in use problem was seen during #5:comment:20
    https://trac.hep.caltech.edu/trac/fdtcp/ticket/5#comment:20
    2 times out of 338 transfer (attempts). Probably, when there is
    traffic the port can't be bound immediately even if it was
    released very short ago by the previous process.
    This test could not reproduce the problem (when reusing immediately
    the same port number for the next request), so FDTD.getFreePort()
    was reimplemented to reserver ports on round-robin basis.
    
    """
    hostName = os.uname()[1]
    f = getTempFile(functionalFDTDConfiguration)
    inputOption = "--config=%s" % f.name
    conf = ConfigFDTD(inputOption.split())
    conf.sanitize()
    testName =  inspect.stack()[0][3]
    logger = Logger(name=testName,
                    logFile="/tmp/fdtdtest-%s.log" % testName,
                    level=logging.DEBUG)
    apMon = None
    fdtd = FDTD(conf, apMon, logger)
    
    # launch two subsequent ReceivingServerAction, second will likely fail
    # to bind the same, just very short ago, released port
    serverId = "%s" % testName
    testAction  = TestAction(hostName, hostName)
    testAction.id = serverId
    # do TestAction 
    r = fdtd.service.service(testAction)
    assert r.status == 0
    options = dict(gridUserDest="someuserDest",
                   clientIP=os.uname()[1],
                   destFiles=[])    
    recvServerAction = ReceivingServerAction(testAction.id, options)
    # do ReceivingServerAction - start FDT Java server
    r = fdtd.service.service(recvServerAction)
    print r.msg
    assert r.status == 0
    assert r.serverPort == 54321
    cleanupAction = CleanupProcessesAction(serverId,
                                           timeout=0,
                                           waitTimeout=False)
    # do CleanupProcessesAction - shut FDT Java server, port shall be
    # released
    r = fdtd.service.service(cleanupAction)
    print r.msg
    assert r.status == 0
    # do another ReceivingServerAction - start FDT Java server
    r = fdtd.service.service(recvServerAction)
    print r.msg
    assert r.status == 0
    # will not get the same port, but the next one in the range
    assert r.serverPort == 54322
    
    # in fact, if separate log files are enabled, after this last
    # ReceivingServerAction, there is a separate log file open.
    # taking the the service down, it should also closed it's related
    # to open files #41 problem
    fdtd.shutdown()
    fdtd.pyroDaemon.closedown()
    logger.close()
    
    
def testFDTDPortReservation():
    """
    Port reservation algorithm reimplemented while on
    #38 - Address already in use FDT Java
    https://trac.hep.caltech.edu/trac/fdtcp/ticket/38
    
    """
    # configuration value may be
    portRangeStrFDTServer = "54321,54330"
    portMin, portMax = [int(i) for i in portRangeStrFDTServer.split(',')]
    portMgmt = PortReservation(portMin, portMax)
    
    assert len(portMgmt._ports) == 10
    assert portMgmt._numTakenPorts == 0
    assert portMgmt._ports[0]._port == 54321
    assert portMgmt._ports[9]._port == 54330
    
    # existing port, but hasn't been reserved before
    py.test.raises(PortReservationException, portMgmt.release, 54321)
    
    for portInput, index in zip(range(54321, 54330 + 1), range(11)):
        p = portMgmt.reserve()
        assert p == portInput
        assert portMgmt._numTakenPorts == index + 1
        assert portMgmt._ports[index]._reservedTimes == 1
        assert portMgmt._ports[index]._reservedNow == True
        
    py.test.raises(PortReservationException, portMgmt.reserve)
    py.test.raises(PortReservationException, portMgmt.release, 1000)
    
    for port, index in zip(range(54321, 54326), range(6)):
        portMgmt.release(port)
        assert portMgmt._ports[index]._reservedTimes == 1
        assert portMgmt._ports[index]._reservedNow == False
    
    for port, index in zip(range(54321, 54325), range(5)):
        p = portMgmt.reserve()
        assert p == port
        assert portMgmt._ports[index]._reservedTimes == 2
        assert portMgmt._ports[index]._reservedNow == True
        

def testFDTDServiceOpenFilesFullTransfer():
    """
    #41:comment:8 - Too many open files (fdtd side)
    SendingClient actually removed itself from the executors container
    once it finishes so subsequent CleanupProcessesAction doesn't know
    about this process, nor about its open separate log file, which
    doesn't get closed.
    
    Simulate a simple successful transfer, send all actions and
    check number of open files - does all as it happens in fdtd.service()
    
    """
    hostName = os.uname()[1]
    testName =  inspect.stack()[0][3]
    initStateNumOpenFilesTestStart, filesStr = getOpenFilesList()
    print("%s: test 0: open files: %s items:\n%s" %
         (testName, initStateNumOpenFilesTestStart, filesStr))
    # there should not be any open files now
    assert initStateNumOpenFilesTestStart == 0
    
    f = getTempFile(functionalFDTDConfiguration)
    inputOption = "--config=%s --port=10001" % f.name
    confServer = ConfigFDTD(inputOption.split())
    confServer.sanitize()
    loggerServer = Logger(name=testName,
                          logFile="/tmp/fdtdtest-%s-writer.log" % testName,
                          level=logging.DEBUG)
    apMon = None
    fdtdServer = FDTD(confServer, apMon, loggerServer)

    inputOption = "--config=%s --port=10002" % f.name
    confReader = ConfigFDTD(inputOption.split())
    confReader.sanitize()
    loggerReader = Logger(name=testName,
                          logFile="/tmp/fdtdtest-%s-reader.log" % testName,
                          level=logging.DEBUG)
    apMon = None
    fdtdReader = FDTD(confReader, apMon, loggerReader)
    
    # -2 open log files, additional -1 is the temp config file
    initStateNumOpenFiles, filesStr = getOpenFilesList()
    print("%s: test 1: open files: %s items:\n%s" %
          (testName, initStateNumOpenFiles, filesStr))
    assert initStateNumOpenFilesTestStart == initStateNumOpenFiles - 2 - 1
    
    testActionServer  = TestAction(hostName, hostName)
    testActionServer.id = testActionServer.id + "-writer"
    r = fdtdServer.service.service(testActionServer)
    assert r.status == 0
    options = dict(gridUserDest="someuserDest",
                   clientIP=os.uname()[1],
                   destFiles=["/dev/null"])    
    recvServerAction = ReceivingServerAction(testActionServer.id, options)
    r = fdtdServer.service.service(recvServerAction)
    print r.msg
    assert r.status == 0
    serverFDTPort = r.serverPort
    
    # there should be only 1 extra opened file now - ReceivingServerAction
    # separate log
    numOpenFilesNow, filesStr = getOpenFilesList()
    print("%s: test 2: open files: %s items:\n%s" %
          (testName, numOpenFilesNow, filesStr))
    assert initStateNumOpenFiles == numOpenFilesNow - 1
    
    testActionReader  = TestAction(hostName, hostName)
    testActionReader.id = testActionReader.id + "-reader"    
    r = fdtdReader.service.service(testActionReader)
    assert r.status == 0
    files = [TransferFile("/etc/passwd", "/dev/null")] # list of TransferFile
    options = dict(port=serverFDTPort,
                   hostDest=os.uname()[1],
                   transferFiles=files,
                   gridUserSrc="soemuserSrc")
    sndClientAction = SendingClientAction(testActionReader.id, options)
    r = fdtdReader.service.service(sndClientAction)
    assert r.status == 0
    
    # there should be +2 extra - for separate both server and client
    numOpenFilesNow, filesStr = getOpenFilesList()
    print("%s: test 3: open files: %s items:\n%s" %
          (testName, numOpenFilesNow, filesStr))
    # 2 extra files - separate transfer log at both ends            
    assert initStateNumOpenFiles == numOpenFilesNow - 2
    
    # now the transfer is over, both server (writer) and sender (reader)
    # parties kept their separate log files open, CleanupProcessesAction
    # will close them
        
    print "going to clean up"
    cl = CleanupProcessesAction(testActionReader.id, waitTimeout=False)
    r = fdtdReader.service.service(cl)
    assert r.status == 0
    
    # one shall be closed now
    numOpenFilesNow, filesStr = getOpenFilesList()
    print("%s: test 4: open files: %s items:\n%s" %
          (testName, numOpenFilesNow, filesStr))        
    assert initStateNumOpenFiles == numOpenFilesNow - 1
    
    cl = CleanupProcessesAction(testActionServer.id, waitTimeout=False)
    r = fdtdServer.service.service(cl)
    assert r.status == 0
    
    # both separate log files should be closed now
    # problem #41:comment:8 was here - server behaved correctly, but
    # reader kept its separate log file open
    numOpenFilesNow, filesStr = getOpenFilesList()
    print("%s: test 5: open files: %s items:\n%s" %
          (testName, numOpenFilesNow, filesStr))    
    assert initStateNumOpenFiles == numOpenFilesNow
    
    fdtdServer.shutdown()
    fdtdServer.pyroDaemon.closedown()
    loggerServer.close()

    fdtdReader.shutdown()
    fdtdReader.pyroDaemon.closedown()
    loggerReader.close()
    
    # after even log files were closed, etc
    numOpenFilesNow, filesStr = getOpenFilesList()
    print("%s: test 6: open files: %s items:\n%s" %
          (testName, numOpenFilesNow, filesStr))
    # -1: the temp configuration file is still open        
    assert initStateNumOpenFilesTestStart == numOpenFilesNow - 1
    

def testMainLogFileOpeningDuringDaemonisation():
    py.test.skip("Test skipped, messes up with input/output streams for "
                 "other test, better to run it stand-alone: "
                 "py.test fdtcplib/test/test_fdtd.py -s -k  testMainLogFileOpeningDuringDaemonisation")
    """
    As described in the problem #41:comment:9, the main log file remains
    open thrice (under different descriptor) after initial daemonisation.

    In order to include this particular test into whole test suite running
    (issue with file descriptors being redirected, etc in fdtd.daemonize()
    function), perhaps after running this test, the file descriptors
    can be put back from backup sys.__stdout__, etc?
    
    """
    c = """
[general]
logFile = /tmp/fdtd.log
pidFile = /tmp/fdtd.pid
"""
    testName =  inspect.stack()[0][3]
    f = getTempFile(c)
    inputOption = "--config=%s" % f.name
    conf = ConfigFDTD(inputOption.split())
    f.close()
    logFile = "%s-%s" % (conf.get("logFile"), testName)
    pidFile = conf.get("pidFile")
    if os.path.exists(logFile):
        print("test: %s: file '%s' exists, removing ..." %
              (testName, logFile))
        os.remove(logFile)
    if os.path.exists(pidFile):
        print("test: %s: file '%s' exists, removing ..." %
              (testName, pidFile))
        os.remove(pidFile)
    logger = Logger(name=testName, logFile=logFile, level=logging.DEBUG)
    
    logger.debug("Before daemonization ...")
    numFiles, filesStr = getOpenFilesList()
    logger.debug("Logging open files: %s items:\n%s" % (numFiles, filesStr))
    
    try:
        daemonize(conf, logger)
    except SystemExit:
        # previous leading process continues here
        return

    # here continues the newly created background daemon
    f = open(pidFile, 'r')
    rc = f.read()
    f.close()
    rc = rc.strip()
    pid = int(rc)
    
    numFiles, filesStr = getOpenFilesList()
    logger.debug("Logging open files: %s items:\n%s" % (numFiles, filesStr))
    logger.debug("Before finishing ... ")
    logger.close()
    # the log file may be open more times due to streams descriptor
    # duplication as done in fdtd.daemonization() but now, once is
    # closed, there should not any other outstanding open file
    assert numFiles == 0
