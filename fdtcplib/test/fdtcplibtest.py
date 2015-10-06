"""
Functional tests for fdtd daemon which can't be run
via py.test (or it's complicated).
Combined functional tests calling methods from fdtcp - running
the the whole transfer starting from fdtcp.

__author__ = Zdenek Maxa

"""


import os
import sys
import tempfile
import signal
import logging
import time
import tempfile
import traceback
import threading
import socket

import Pyro
import Pyro.core
from Pyro.errors import PyroError

import psutil
from psutil import Process
from psutil import NoSuchProcess

from fdtcplib.fdtcp import FDTCopy
from fdtcplib.fdtcp import ConfigFDTCopy
from fdtcplib.fdtcp import Transfer
from fdtcplib.fdtcp import Transfers
from fdtcplib.fdtd import FDTD
from fdtcplib.fdtd import ConfigFDTD
from fdtcplib.fdtd import AuthService
from fdtcplib.common.errors import FDTDException
from fdtcplib.common.errors import AuthServiceException
from fdtcplib.common.errors import PortReservationException
from fdtcplib.common.errors import ServiceShutdownBySignal
from fdtcplib.common.actions import TestAction
from fdtcplib.common.actions import ReceivingServerAction
from fdtcplib.common.actions import SendingClientAction
from fdtcplib.common.actions import CleanupProcessesAction
from fdtcplib.common.TransferFile import TransferFile
from fdtcplib.utils.utils import getUserName
from fdtcplib.utils.Logger import Logger
from fdtcplib.utils.Executor import ExecutorException
from fdtcplib.utils.Config import ConfigurationException
from fdtcplib.common.errors import FDTDException
from fdtcplib.common.errors import TimeoutException
from fdtcplib.common.errors import FDTCopyException
from fdtcplib.common.errors import FDTCopyShutdownBySignal



def getTempFile(content):
    """
    Method is used for creating temporary file to store configuration
    for fdtd into.
    
    """
    f = tempfile.NamedTemporaryFile("w+") # read / write
    f.write(content)
    f.flush()
    f.seek(0)
    return f


functionalFDTDConfiguration = \
"""
[general]
port = 9000
portRangeFDTServer = 54321,54400
logFile = /tmp/fdtd.log
pidFile = /tmp/fdtd.pid
daemonize = True
transferSeparateLogFile = False
debug = DEBUG
# notice -notmp option which prevents from creating temp files (.file) which
# is useful e.g. when doing a dummy transfer /dev/zero -> /dev/null
# file fileFile (.null) could not be created
fdtSendingClientCommand = java -jar fdtjava/fdt.jar -P 16 -p %(port)s -c %(hostDest)s -d / -fl %(fileList)s -rCount 5 -notmp -noupdates
fdtSendingClientKillTimeout = 1
fdtReceivingServerCommand = java -jar fdtjava/fdt.jar -bs 64K -p %(port)s -wCount 5 -f %(clientIP)s -S -noupdates
fdtServerLogOutputTimeout = 2
fdtServerLogOutputToWaitFor = "FDTServer start listening on port: %(port)s"
fdtReceivingServerKillTimeout = 1
killCommand = "kill -9 %(pid)s"
killCommandSudo = "kill -9 %(pid)s"

# will not be used in this test, but are mandatory (when doing sanitize() on configuration)
portAuthService = 0
authServiceLogOutputTimeout = 0
authServiceLogOutputToWaitFor = "empty"
authServiceCommand = "empty"

"""


def _fdtd_startApplication(conf, logger):
    """
    This is simplified version of fdtd.startApplication() function.
    It creates daemon.
    
    """    
    # daemonize some stuff taken from fdtd.daemonize    
    logger.info("Preparing for daemonization (parent process "
                "PID: '%s') ..." % os.getpid())
        
    pidFile = conf.get("pidFile")
        
    # check if the pidFile is writeable
    try:
        pidFileDesc = open(pidFile, 'w')
        pidFileDesc.close()
    except IOError, ex:
        logger.fatal("Can't access PID file '%s', reason: %s" %
                     (pidFile, ex))
        logger.close()
        sys.exit(1)
    
    # daemonization forking ...
    if os.fork() != 0:
        return
    
    # decouple from parent environment
    os.setsid()
    os.umask(0)
    # don't change current working directory (os.chdir("/"))

    # fork again so we are not a session leader
    if os.fork() != 0:
        sys.exit(0)

    # output streams redirection into the log file
    # log file is already used by logger, concurrent writes may get messy ...
    # ideally there however should not be any logging into streams
    # from now on ...
    logger.debug("Redirecting stdout, stderr, stdin streams ...")
    logFile = file(conf.get("logFile"), "a+", 0) # buffering - 0 (False)
    devNull = file("/dev/null", 'r')
    os.dup2(logFile.fileno(), sys.stdout.fileno())
    os.dup2(logFile.fileno(), sys.stderr.fileno())
    os.dup2(devNull.fileno(), sys.stdin.fileno())
    
    # finally - the daemon process code, first store it's PID into file
    pid = os.getpid()
    logger.info("Running as daemon process: PID: '%s' (forked), "
                "PID file: '%s'" % (pid, pidFile))
    pidFileDesc = open(pidFile, 'w')
    pidFileDesc.write(str(pid))
    pidFileDesc.close()
    # daemonize method - end
    
    # use DNS names rather than IP address
    Pyro.config.PYRO_DNS_URI = True
    apMon = None
    daemon = None
    try:
        try:
            daemon = FDTD(conf, apMon, logger)
            daemon.start()
        except AuthServiceException, ex:
            logger.fatal("Exception during AuthService startup, "
                         "reason: %s" % ex)
        except (FDTDException, ), ex:
            logger.fatal("Exception during FDTD initialization, "
                         "reason: %s" % ex)
        except KeyboardInterrupt:
            logger.fatal("Interrupted from keyboard ...")
        except ServiceShutdownBySignal:
            logger.fatal("Shutdown exception signal received.")
        except Exception, ex:
            logger.fatal("Exception was caught ('%s'), reason: %s"
                          % (ex.__class__.__name__, ex), traceBack=True)
    finally:
        if daemon:
            try:
                daemon.shutdown()
            except Exception, exx:
                logger.fatal("Exception occurred during shutdown sequence, "
                             "reason: %s" % exx, traceBack=True)
                
        # clean up the pidFile after itself, important for the next test
        # file should exist at this point ...
        logger.info("Attempt to remove pidFile '%s'" % pidFile)
        os.remove(pidFile)
        logger.info("'%s' pidFile removed." % pidFile)
        
        logger.close()        
        
        # important (one of the things impossible via py.test yet
        # can't run everything again in the parent process method)
        sys.exit(0)
        
        
        
def startFDTDService(testName, configLine):
    f = getTempFile(functionalFDTDConfiguration)
    inputOption = "--config=%s %s"  % (f.name, configLine)
    print "%s -- inputOption: '%s'" % (testName, inputOption)
    
    conf = ConfigFDTD(inputOption.split())
    conf.sanitize()
    
    # realizing that
    # #Exception OSError: (2, 'No such file or directory', '/tmp/tmpmKK9nm')
    # in <bound method _TemporaryFileWrapper.__del__ of
    # <closed file '<fdopen>', mode 'w+' at 0x1ddf8b0>> ignored
    # is a different issue from the initial one
    # ValueError: I/O operation on closed file took over half a day of
    # experiments and tests, solution is to get rid of this tempfile
    # as soon as possible:
    del f
    
    waitUntilProcessFinished(conf.get("pidFile"), testName)
            
    logger = Logger(name=testName,
                    logFile=conf.get("logFile"),
                    level=conf.get("debug"))
    logger.info(60 * '#')
    logger.info(60 * '#')
    
    print "%s -- starting background daemon process ..." % testName
    _fdtd_startApplication(conf, logger)
    
    print "%s -- main process continues ..." % testName
        
    pidFile = conf.get("pidFile")
    # have to wait until daemon puts its PID into a file
    pidStr = ''
    while pidStr == '':
        if not os.path.exists(pidFile):
            continue
        pidStr = open(pidFile, 'r').read()
        time.sleep(0.1)
    pid = int(pidStr)
    print ("%s -- reading pidFile '%s', content: '%s'" % (testName,
                                                          pidFile,
                                                          pidStr))
    checkAndBlockUntilProcessBoundPort(conf.get("port"),
                                       pid,
                                       testName=testName)
    print "%s -- daemon should be running now" % testName
    return pid, conf, logger
      


def testFDTD(files,
             port=9000,
             testName=None,
             doCleanup=False,
             interrupt=False):
    """
    This test is calls immediately startFDTDService which uses daemon
    process - forking as it happens in fdtd.py.
    
    """
    # this logger is fdtd logger (fdtd.log)
    configLine = ("--port=%s --logFile=/tmp/fdtd.log --pidFile=/tmp/fdtd.pid "
                  "--transferSeparateLogFile" % port)
    pid, conf, logger = startFDTDService(testName, configLine)
        
    # now contact the daemon service
    hostName = os.uname()[1]
    loggerClient = Logger(name=testName,
                          logFile="/tmp/fdtcp.log",
                          level=conf.get("debug"))
    uri = "PYROLOC://" + hostName + ":" + str(port) + "/FDTDService"
    
    fdtcp = FDTCopy(uri, loggerClient)
    testAction = TestAction(hostName, hostName, timeout = 3)
    fdtcp.perform(testAction)
    
    # create ReceivingServerAction
    # destFiles - list if files at destination - just check (#36)
    destFiles = [f.fileDest for f in files] 
    options = dict(gridUserDest = "someuserDest", clientIP = os.uname()[1],
                   destFiles = destFiles)
    serverId = testAction.id + "-server"
    recvServerAction = ReceivingServerAction(serverId, options)
    result = fdtcp.perform(recvServerAction)
    assert result.serverPort == 54321
    assert result.host == os.uname()[1]

    # try creating sending client within the same FDTD daemon
    options = dict(port = result.serverPort, hostDest = result.host,
                   transferFiles = files, gridUserSrc = "someuserSrc")
    clientId = testAction.id + "-client"
    sndClientAction = SendingClientAction(clientId, options)

    # for the case it would fail with error
    try:
        if interrupt:
            signal.signal(signal.SIGALRM, raiseTimeoutException)
            signal.alarm(4) # raise alarm in timeout seconds
        # TimeoutException which will be raised during FDTCopy.perform()
        # will actually translate into FDTCopyException
        fdtcp.perform(sndClientAction)
    except (FDTCopyException, FDTDException), ex:
        print "%s - exception occured:" % testName
        print ex
    
    print "%s -- after transfer point" % testName
    
    if doCleanup:
        print ("%s -- creating new proxy (previous hags/was "
               "interrupted) ..." % testName)
        # since both FDT Java server, client have 1s min.for finish,
        # give another 1s for overhead 
        
        # issue: since the above all might have been interrupted by an
        # alarm (5-OKTransferCleanup test), the PYRO client (proxy) seems
        # not re-usable
        # here for sending CleanupProcessesAction. Clean up is times out
        # and is even not
        # received by the fdtd, need to create a new proxy (client).
        # ticket #26
        fdtcpClean = FDTCopy(uri, loggerClient)
        cleanupAction = CleanupProcessesAction(serverId, timeout=2)
        fdtcpClean.perform(cleanupAction)
        
        cleanupAction = CleanupProcessesAction(clientId, timeout=2)
        fdtcpClean.perform(cleanupAction)
        
        # test related to #8 - try killing processes which were already
        # killed should check for "OSError: [Errno 10] No child processes"
        cleanupAction = CleanupProcessesAction(serverId, timeout=2)
        fdtcpClean.perform(cleanupAction)
        
        cleanupAction = CleanupProcessesAction(clientId, timeout=2)
        fdtcpClean.perform(cleanupAction)
            
    # shutdown the service
    print "%s -- calling kill ... end" % testName
    os.kill(pid, signal.SIGTERM)
    loggerClient.close()



class SignalThread(threading.Thread):
    """
    Thread for sending signals.
    
    """
    def __init__(self, pid, sigType, timeoutBeforeSending=3):
        threading.Thread.__init__(self)
        self.wherePid = pid
        self.sigType = sigType
        self.timeoutBeforeSending = timeoutBeforeSending
        print "SignalThread initialized."

    def run(self):
        print ("SignalThread - running (waiting: %ss) " %
               self.timeoutBeforeSending)
        time.sleep(self.timeoutBeforeSending)
        os.kill(self.wherePid, self.sigType)
        print "SignalThread - signal sent"
        
    
    
def testFdtcpSignalHandling(files, ports, testName=None):
    """
    Test will create two independent FDTD services.
    Tests signal handling at fdtcp - terminating progressing transfer.
    This test is very similar to testfdtcpFdt() but due to having two FDTD
    service, it can call more code directly from the fdtcp client (fewer
    copied code).
    #32 fdtcp - signal handling
    
    """
    configLine = ("--port=%s --logFile=/tmp/fdtdDst-%s.log "
                  "--pidFile=/tmp/fdtdDst.pid" % (ports[0], testName))
    pidDst, confDst, loggerDst = startFDTDService(testName, configLine)
    configLine = ("--port=%s --logFile=/tmp/fdtdSrc-%s.log "
                  "--pidFile=/tmp/fdtdSrc.pid" % (ports[1], testName))
    pidSrc, confSrc, loggerSrc = startFDTDService(testName, configLine)
    
    loggerDst.debug("Configuration values (processed):\n%s" %
                    loggerDst.pprintFormat(confDst._options))
    loggerSrc.debug("Configuration values (processed):\n%s" %
                    loggerSrc.pprintFormat(confSrc._options))
    
    # now client, fdtcp stuff
    host = os.uname()[1]
    inputOption = ("--logFile=/tmp/fdtcp-%s.log fdt://%s:%s%s "
                   "fdt://%s:%s%s" %
                   (testName,
                    host,
                    ports[1],
                    files[0].fileSrc,
                    host,
                    ports[0],
                    files[0].fileDest))
    print "%s -- inputOption: '%s'" % (testName, inputOption)
    confClient = ConfigFDTCopy(inputOption.split())
    confClient.sanitize()
    loggerClient = Logger(name=testName,
                          logFile=confClient.get("logFile"),
                          level=confClient.get("debug"))
    apMon = None
    transfers = Transfers(confClient, apMon, loggerClient)
    
    # catch whatever exception so that fdtd is definitely stopped at the end
    try:
        try:
            for transfer in transfers.transfers.values():
                # transfer.performTransfer() - can't do this - will fail on
                #    1) authentication
                testAction = TestAction(host, host, 1)
                transfer.id = testAction.id
                transfer.receiver.perform(testAction)
                transfer.sender.perform(testAction)
                
                clientIP = socket.gethostbyname(transfer.hostSrc)
                # destFiles - list if files at destination - just check (#36)
                destFiles = [f.fileDest for f in transfer.files] 
                options = dict(gridUserDest = "<some_remoteGridUserDest>",
                               clientIP = clientIP, destFiles = destFiles)
                # start receiving FDT server
                recvServerAction = ReceivingServerAction(testAction.id,
                                                         options)
                transfer.toCleanup.append(transfer.receiver.uri)
                result = transfer.receiver.perform(recvServerAction)
                serverFDTPort = result.serverPort
                # start sending FDT client which initiates the transfer process
                options = dict(port=serverFDTPort,
                               hostDest=transfer.hostDest,
                               transferFiles=transfer.files,
                               gridUserSrc="<some_remoteGridUserSrc>")
                sndClientAction = SendingClientAction(testAction.id, options)
                # calling the client is synchronous action - waiting until
                # it finishes ...
                # this command will stop the execution flow ...
                # if explicitly stated, this call will be interrupted
                # after timeout give long timeout since the transfer will
                # be terminated by SIGHUP
                fdtcpPid = os.getpid()
                sigThread = SignalThread(fdtcpPid, signal.SIGHUP)
                sigThread.start()
                sndClientAction.timeout = 20000
                transfer.toCleanup.append(transfer.sender.uri)
                try:
                    print "%s -- initiating FDT Java transfer ... " % testName
                    result = transfer.sender.perform(sndClientAction)
                except FDTCopyShutdownBySignal, ex:
                    print ("%s -- exception caught (signal expected): %s" %
                           (testName, ex))                    
                except FDTCopyException, ex:
                    print "%s -- exception caught: %s" % (testName, ex)
                
                loggerDst.debug("LOG CHECK: each FDTD._executors container "
                                "shall have 1 item")
                loggerSrc.debug("LOG CHECK: each FDTD._executors container "
                                "shall have 1 item")
                
                # signal now received and process now: send clean up to
                # terminate transfer
                # as this would happen in fdtcp.main() 
                transfer.performCleanup()                
        except Exception, exx:
            print "%s -- unexpected exception: %s" % (testName, exx)
        else:
            loggerDst.debug("LOG CHECK: each FDTD._executors container "
                            "shall have 0 items")
            loggerSrc.debug("LOG CHECK: each FDTD._executors container "
                            "shall have 0 items")
    finally:
        # shutdown the service
        print "%s -- calling kill (to PID: %s) ... end" % (testName, pidDst)
        os.kill(pidDst, signal.SIGTERM)
        print "%s -- calling kill (to PID: %s) ... end" % (testName, pidSrc)
        os.kill(pidSrc, signal.SIGTERM)
        loggerClient.close()
        
        
def testFdtcpKilledBySignalCorrectTransfers(ports, testName = None):
    """
    See comments when calling the test.
    related to work on ticket #23 - Handle CleanupAction from fdtcp is
    not triggered
    test also #33 - CleanupProcessesAction - attribute to ignore any
    wait-to-finish timeouts
    
    tests with plain FDT Java:
        server: java -jar fdtjava/fdt.jar -noupdates -bs 64K -wCount 5 -p 54321
        client:  time java -jar fdtjava/fdt.jar -P 16 -p 54321 -rCount 5 -notmp -noupdates -c localhost -d /tmp/fdtdtest /mnt/data/ottova_encyklopedie/OEOV/*
        lasted ~20s on ~600MB of data in ~310 files
        
    TODO:
        the fact that FDT Java server, running with -S remains as zombie
        even after successful transfer should be finished with Ramiro
        it will only remain hanging if there is no CleanupProcessesAction
        sent from fdtcp, which should
        now: #32 - fdtcp - signal handling
    
    """
    def createCopyJobFile(inputPath,
                          outputPath,
                          copyJobFileName,
                          urlSrc,
                          urlDst):
        """
        Doesn't perform any additional checks whether items in a directory are
        only files, etc.
        
        """
        cjf = open(copyJobFileName, 'w')
        files = os.listdir(inputPath)
        for f in files:
            src = "%s%s" % (urlSrc, os.path.join(inputPath, f))
            dst = "%s%s" % (urlDst, os.path.join(outputPath, f))
            cjf.write("%s %s\n" % (src, dst))
        cjf.close()
    
    host = os.uname()[1]    
    inputPath = "/mnt/data/ottova_encyklopedie/OEOV"
    outputPath = "/tmp/fdtdtest"
    copyJobFileName = "/tmp/fdtcp-copyjobfile-%s" % testName
    urlSrc = "fdt://%s:%s" % (host, ports[1])
    urlDst = "fdt://%s:%s" % (host, ports[0])
    createCopyJobFile(inputPath, outputPath, copyJobFileName, urlSrc, urlDst)
        
    # start a pair of FDTD services
    configLine = ("--port=%s --logFile=/tmp/fdtdDst-%s.log "
                  "--pidFile=/tmp/fdtdDst.pid" % (ports[0], testName)) 
    pidDst, confDst, loggerDst = startFDTDService(testName, configLine)
    configLine = ("--port=%s --logFile=/tmp/fdtdSrc-%s.log "
                  "--pidFile=/tmp/fdtdSrc.pid" % (ports[1], testName))
    pidSrc, confSrc, loggerSrc = startFDTDService(testName, configLine)
    
    loggerDst.debug("Configuration values (processed):\n%s" %
                    loggerDst.pprintFormat(confDst._options))
    loggerSrc.debug("Configuration values (processed):\n%s" %
                    loggerSrc.pprintFormat(confSrc._options))
    
    # now client, fdtcp stuff
    inputOption = ("--logFile=/tmp/fdtcp-%s.log --copyjobfile=%s" %
                   (testName, copyJobFileName))
    print "%s -- inputOption: '%s'" % (testName, inputOption)
    confClient = ConfigFDTCopy(inputOption.split())
    confClient.sanitize()
    loggerClient = Logger(name=testName,
                          logFile=confClient.get("logFile"),
                          level=confClient.get("debug"))
    apMon = None
    transfers = Transfers(confClient, apMon, loggerClient)
    
    # catch whatever exceptions
    try:
        try:
            for transfer in transfers.transfers.values():
                # transfer.performTransfer() - can't do this - will fail on
                #    1) authentication
                testAction = TestAction(host, host, 1)
                transfer.id = testAction.id
                transfer.receiver.perform(testAction)
                transfer.sender.perform(testAction)
                
                clientIP = socket.gethostbyname(transfer.hostSrc)
                # destFiles - list if files at destination - just check (#36)
                destFiles = [f.fileDest for f in transfer.files]
                options = dict(gridUserDest = "<some_remoteGridUserDest>",
                               clientIP = clientIP, destFiles = destFiles)
                # start receiving FDT server
                recvServerAction = ReceivingServerAction(testAction.id, options)
                transfer.toCleanup.append(transfer.receiver.uri)
                result = transfer.receiver.perform(recvServerAction)
                serverFDTPort = result.serverPort
                # start sending FDT client which initiates the transfer process
                options = dict(port=serverFDTPort,
                               hostDest=transfer.hostDest,
                               transferFiles=transfer.files,
                               gridUserSrc="<some_remoteGridUserSrc>")
                sndClientAction = SendingClientAction(testAction.id, options)
                # calling the client is synchronous action - waiting until
                # it finishes ... this command will stop the execution
                # flow ...
                # if explicitly stated, this call will be interrupted after
                # timeout give long timeout since the transfer will be
                # terminated by SIGHUP
                fdtcpPid = os.getpid()
                sigThread = SignalThread(fdtcpPid,
                                         signal.SIGHUP,
                                         timeoutBeforeSending=4)
                sigThread.start()
                sndClientAction.timeout = 20000
                transfer.toCleanup.append(transfer.sender.uri)
                try:
                    print "%s -- initiating FDT Java transfer ... " % testName
                    result = transfer.sender.perform(sndClientAction)
                except FDTCopyShutdownBySignal, ex:
                    print ("%s -- exception caught (signal expected): "
                           "%s" % (testName, ex))                    
                except FDTCopyException, ex:
                    print "%s -- exception caught: %s" % (testName, ex)
                
                # signal now received and process now: send clean up to
                # terminate transfer
                # as this would happen in fdtcp.main()
                # calling cleanup would be to terminate remote processes
                #     (no waiting - kill immediately)
                # transfer.performCleanup(waitTimeout = False)
                
                #print "%s -- hard kill of myself, current process
                # (as if fdtcp gets SIGKILL) ... " % testName
                #os.kill(fdtcpPid, signal.SIGKILL) # no chance to react
                print "%s -- sending clean up ..." % testName
                # as implemented in fdtcp signal handling
                transfer.performCleanup(waitTimeout=False)
                
        except Exception, exx:
            print "%s -- unexpected exception: %s" % (testName, exx)
    finally:
        # shutdown the service
        print "%s -- finally branch." % testName
        # do not kill anything here (in this specific test)
        """
        print "%s -- calling kill (to PID: %s) ... end" % (testName, pidDst)
        os.kill(pidDst, signal.SIGTERM)
        print "%s -- calling kill (to PID: %s) ... end" % (testName, pidSrc)
        os.kill(pidSrc, signal.SIGTERM)
        """
        loggerClient.close()
        
  
def testFdtdShutdownForced(files, ports, testName=None):
    """
    ticket #27 - fdtd - finish signal handler, distinguish shutdown,
        shutdown-forced
    Test creates a pair of FDTD services and initiates successful never
    ending transfer.
    During the transfer, FDTD processes receive signals:
        1) SIGHUP (1) which only gets logged (running processes are checked
            and logged) and is ignored - transfer doesn't get terminated
            test that both daemons are still running
        2) SIGTERM (15) logs running transfers (if any) and both daemons
            along with their possible transfer subprocesses are
            terminated, test that both daemon processes finished
    
    """
    configLine = ("--port=%s --logFile=/tmp/fdtdDst-%s.log "
                  "--pidFile=/tmp/fdtdDst.pid" % (ports[0], testName)) 
    pidDst, confDst, loggerDst = startFDTDService(testName, configLine)
    configLine = ("--port=%s --logFile=/tmp/fdtdSrc-%s.log "
                  "--pidFile=/tmp/fdtdSrc.pid" % (ports[1], testName))
    pidSrc, confSrc, loggerSrc = startFDTDService(testName, configLine)
    
    loggerDst.debug("Configuration values (processed):\n%s" %
                    loggerDst.pprintFormat(confDst._options))
    loggerSrc.debug("Configuration values (processed):\n%s" %
                    loggerSrc.pprintFormat(confSrc._options))
    
    # now client, fdtcp stuff
    host = os.uname()[1]
    inputOption = ("--logFile=/tmp/fdtcp-%s.log fdt://%s:%s%s "
                   "fdt://%s:%s%s" %
                   (testName,
                    host,
                    ports[1],
                    files[0].fileSrc,
                    host,
                    ports[0],
                    files[0].fileDest))
    print "%s -- inputOption: '%s'" % (testName, inputOption)
    confClient = ConfigFDTCopy(inputOption.split())
    confClient.sanitize()
    loggerClient = Logger(name=testName,
                          logFile=confClient.get("logFile"),
                          level=confClient.get("debug"))
    apMon = None
    transfers = Transfers(confClient, apMon, loggerClient)
    
    # catch whatever exception so that fdtd is definitely stopped at the end
    try:
        try:
            for transfer in transfers.transfers.values():
                # transfer.performTransfer() - can't do this - will fail on
                #    1) authentication
                testAction = TestAction(host, host, timeout=1)
                transfer.id = testAction.id
                transfer.receiver.perform(testAction)
                transfer.sender.perform(testAction)
                
                clientIP = socket.gethostbyname(transfer.hostSrc)
                
                # destFiles - list if files at destination - just check (#36)
                destFiles = [f.fileDest for f in transfer.files] 
                options = dict(gridUserDest="<some_remoteGridUserDest>",
                               clientIP=clientIP,
                               destFiles=destFiles)
                # start receiving FDT server
                recvServerAction = ReceivingServerAction(testAction.id,
                                                         options)
                result = transfer.receiver.perform(recvServerAction)
                transfer.toCleanup.append(transfer.receiver.uri)
                serverFDTPort = result.serverPort
                # start sending FDT client which initiates the
                # transfer process
                options = dict(port=serverFDTPort,
                               hostDest=transfer.hostDest,
                               transferFiles=transfer.files,
                               gridUserSrc="<some_remoteGridUserSrc>")
                sndClientAction = SendingClientAction(testAction.id, options)
                # calling the client is synchronous action - waiting until
                # it finishes ...
                # this command will stop the execution flow ...
                transfer.toCleanup.append(transfer.sender.uri)
                print "%s -- initiating FDT Java transfer ... " % testName
                signal.alarm(2)
                try:
                    result = transfer.sender.perform(sndClientAction)
                except FDTCopyException, ex:
                    print ("%s -- exception caught (timeout expected): %s" %
                           (testName, ex))
                
                print("%s -- transfer should be progressing anyway, "
                      "testing signals now ... " % testName)
                print("%s -- testing signal %s ..." %
                      (testName, signal.SIGHUP))
                os.kill(pidDst, signal.SIGHUP)
                os.kill(pidSrc, signal.SIGHUP)
                # on SIGHUP, when there is a transfer in progress, it
                # should not be interrupted -> wait a bit and test that
                # both services are running
                time.sleep(1)
                # allow a bit longer timeout (CPU on this transfer gets 100%)
                testAction = TestAction(host, host, timeout=2)
                result = transfer.receiver.perform(testAction)
                assert result.id == testAction.id
                assert result.status == 0
                # also need to create new fdtcp PYRO proxy, using just
                # result = transfer.sender.perform(testAction) will always
                # time out, although
                # result = transfer.receiver.perform(testAction) would OK
                # (see above) since on the receiver it's not blocking ...
                newSender = FDTCopy(transfer.sender.uri, transfer.logger)
                result = newSender.perform(testAction)
                assert result.id == testAction.id
                assert result.status == 0
                print("%s -- test signal %s ok, both FDTD services still "
                      "running" % (testName, signal.SIGHUP))
                print "%s -- testing signal %s ..." % (testName,
                                                       signal.SIGTERM)
                os.kill(pidDst, signal.SIGTERM)
                os.kill(pidSrc, signal.SIGTERM)
                # on SIGTERM - FDTD services should shut whether or not 
                # there is a progressing transfer wait a bit and test that
                # both services are shut
                time.sleep(1)
                for pidTest in (pidDst, pidSrc):
                    try:
                        p = Process(pidTest)
                        m = ("%s -- error, process %s exists when it "
                             "should not." % (testName, pidTest))
                        print m
                        raise Exception(m)
                    except NoSuchProcess, ex:
                        print ("%s -- testing signals on process PID:%s "
                               "OK - not running" % (testName, pidTest))            
        except Exception, exx:
            print "%s -- unexpected exception: %s" % (testName, exx)
    finally:
        # both FDTD services shall be shut by now
        print "%s -- finally clause." % testName
        loggerClient.close()
        
    # start one FDTD service again and test that it shuts on
    # SIGHUP even if there is no progressing transfer (yes AuthService,
    # executor is normally all the time in the executors container
    # and in this case has to be ignored and service shut anyway)
    # NB startFDTDService() can't be called from within try-finally,
    # otherwise finally clause will be run multiple times ...
    print ("%s -- testing signal %s on 1 service without any "
           "transfer" % (testName, signal.SIGHUP))
    configLine = ("--port=%s --logFile=/tmp/fdtdLast-%s.log "
                  "--pidFile=/tmp/fdtdLast.pid" % (ports[0], testName)) 
    pidLast, confLast, loggerLast = startFDTDService(testName, configLine)
    print "%s -- sending signal %s ..." % (testName, signal.SIGHUP) 
    os.kill(pidLast, signal.SIGHUP)                
    time.sleep(2)
    try:
        p = Process(pidLast)
        m = ("%s -- error, process %s exists when it should "
             "not." % (testName, pidLast))
        print m
        raise RuntimeError(m)
    except NoSuchProcess, ex:
        print("%s -- testing signal on process PID:%s OK - not "
              "running" % (testName, pidLast))

    print "%s -- test finished." % testName
  
  
def testfdtcpFdt(files, port=8000, testName=None):
    """
    Does more combined actions - transfers initiated from fdtcp classes.
    Tries to run as much stuff from fdtcp when doing a transfer as possible.
    Copy & Paste crucial stuff from
    fdtcp.Transfer.[performTransfer,performCleanup]
    (due to authentication and duplicate transfer id issues, can't call
    methods directly).
    
    """
    # this logger is fdtd logger (fdtd.log)
    configLine = ("--port=%s --logFile=/tmp/fdtd.log "
                  "--pidFile=/tmp/fdtd.pid --transferSeparateLogFile" % port)
    pid, conf, logger = startFDTDService(testName, configLine)
    
    # now client, fdtcp stuff
    host = os.uname()[1]
    inputOption = ("--logFile=/tmp/fdtcp.log fdt://%s:%s%s fdt://%s:%s%s" %
                   (host,
                    port,
                    files[0].fileSrc,
                    host,
                    port,
                    files[0].fileDest))
    print "%s -- inputOption: '%s'" % (testName, inputOption)
    confClient = ConfigFDTCopy(inputOption.split())
    confClient.sanitize()
    loggerClient = Logger(name=testName,
                          logFile=confClient.get("logFile"),
                          level=confClient.get("debug"))
    apMon = None
    transfers = Transfers(confClient, apMon, loggerClient)
    
    # catch whatever exception so that fdtd is definitely stopped at the end
    try:
        try:
            for transfer in transfers.transfers.values():
                # transfer.performTransfer() - can't do this - will fail on
                #    1) authentication
                #    2) on transfer id (FDT Java app) already registered
                #       with a single fdtd instance, thus have to have
                #       two distinct transfer ids
                testAction = TestAction(host, host, 1)
                transfer.receiver.perform(testAction)
                transfer.sender.perform(testAction)
                
                clientIP = socket.gethostbyname(transfer.hostSrc)
                # destFiles - list if files at destination - just check (#36)
                destFiles = [f.fileDest for f in transfer.files] 
                options = dict(gridUserDest = "<some_remoteGridUserDest>",
                               clientIP = clientIP, destFiles = destFiles)
                # start receiving FDT server
                recvServerAction = ReceivingServerAction(testAction.id +
                                                         "-server", options)
                result = transfer.receiver.perform(recvServerAction)
                serverFDTPort = result.serverPort
                # start sending FDT client which initiates the transfer process
                options = dict(port=serverFDTPort,
                               hostDest=transfer.hostDest,
                               transferFiles=transfer.files,
                               gridUserSrc="<some_remoteGridUserSrc>")
                sndClientAction = (SendingClientAction(testAction.id +
                                   "-client", options))
                # calling the client is synchronous action - waiting until
                # it finishes ...
                # this command will stop the execution flow ...
                # if explicitly stated, this call will be interrupted after
                # timeout
                sndClientAction.timeout = 2
                try:
                    print "%s -- initiating FDT Java transfer ... " % testName
                    result = transfer.sender.perform(sndClientAction)
                except FDTCopyException, ex:
                    print ("%s -- exception caught (timeout expected "
                           "here): %s" % (testName, ex))
                
                # now send cleanup action to both parties
                # performCleanup re-initializes client pyro proxies:
                #    transfer.receiver.uri
                #    transfer.sender.uri
                # transfer.performCleanup() knows only one transfer id whereas
                # in this test, there id-client, id-server, do what 
                # performCleanup does ...
                # if sending CleanupProcessesAction here (2x) would be 
                # commented out as well as killing the daemon - it's obvious
                # the transfer runs uninterrupted, so the 
                # CleanupProcessesAction interrupts it as intended
                print "%s -- performing clean up ... " % testName
                cl = CleanupProcessesAction(testAction.id + "-client",
                                            timeout=2)
                try:
                    fdtCopyClean = FDTCopy(transfer.receiver.uri,
                                           loggerClient)
                    fdtCopyClean.perform(cl)
                    fdtCopyClean.proxy._release()
                except FDTCopyException, ex:
                    print ("%s -- exception During clean up: %s" %
                           (testName, ex))                    
                cl = CleanupProcessesAction(testAction.id + "-server",
                                            timeout=2)
                try:
                    fdtCopyClean = FDTCopy(transfer.sender.uri, loggerClient)
                    fdtCopyClean.perform(cl)
                    fdtCopyClean.proxy._release()
                except FDTCopyException, ex:
                    print ("%s -- exception During clean up: %s" % 
                           (testName, ex))
        except Exception, exx:
            print "%s -- unexpected exception: %s" % (testName, exx)
    finally:
        # shutdown the service
        print "%s -- calling kill ... end" % testName
        os.kill(pid, signal.SIGTERM)
        loggerClient.close()
    

def checkAndBlockUntilProcessBoundPort(port, pid, testName = "<empty>"):
    """
    use psutils provided functionality alike netstat and check that
    certain port (wait until port becomes bound) is taken by a process
    whose PID is in the file pidFile.
    
    """
    print "%s -- checkAndBlockUntilProcessBoundPort ..." % testName
    process = psutil.Process(int(pid))
    # example:
    # connection(fd=115, family=2, type=1, local_address=('10.0.0.1', 48776),
    # remote_address=('93.186.135.91', 80), status='ESTABLISHED')
    bound = False
    while not bound:
        conns = process.get_connections()
        for conn in conns:
            la = conn.local_address
            if la[1] == port:
                print ("%s -- process '%s' bound '%s' (conn: '%s')" %
                       (testName, pid, port, conn))                
                bound = True
                break
        time.sleep(0.2)
    print "%s -- checkAndBlockUntilProcessBoundPort finished." % testName
    


class MyThread(threading.Thread):
    """
    Test thread for running FDTD daemon.
    
    """
    def __init__(self, fdtd):
        threading.Thread.__init__(self)
        self.fdtd = fdtd
        print "MyThread initialized."

    def run(self):
        print "MyThread - starting the daemon"
        self.fdtd.start()
        print "MyThread - end of run() method"
        
    def stop(self):
        print "MyThread - stopping the daemon"
        self.fdtd.shutdown()
        # although this is invoked, and port of the daemon running within
        # a thread released (as reported), the port (here 3000) still appears
        # in the subsequent checks
        print "MyThread - finished"



def testFDTDExecutorDuplicateId(port=9000, testName="RegistTest"):
    """
    Tries to create second Executor process
    with an id which is already registered with FDTD (caller entity).
    This test is using threading.
    
    """
    print "FDTD, Executor id registration test"
    f = getTempFile(functionalFDTDConfiguration)
    inputOption = "--config=%s --port=%s" % (f.name, port)
    print "%s -- inputOption: '%s'" % (testName, inputOption)
    conf = ConfigFDTD(inputOption.split())
    conf.sanitize()
    del f
    
    waitUntilProcessFinished(conf.get("pidFile"), testName)
    
    logger = Logger(name=testName,
                    logFile=conf.get("logFile"),
                    level=conf.get("debug"))
    logger.info(60 * '#')
    logger.info(60 * '#')
    apMon = None
    Pyro.config.PYRO_DNS_URI = True
    daemon = FDTD(conf, apMon, logger)
    t = MyThread(daemon)
    # The entire Python program exits when no active non-daemon threads
    # are left.
    # if commented out, problem waits until thread finishes
    t.setDaemon(True)
    t.start()
    print "%s -- daemon should be running now" % testName
    # create ReceivingServerAction
    # destFiles - list if files at destination - just check (#36)            
    destFiles = ["nonsence"] 
    options = dict(gridUserDest="someuserDest",
                   clientIP=os.uname()[1],
                   destFiles=destFiles)
    id = "somecurrentid"
    recvServerAction = ReceivingServerAction(id, options)
    # unlike of the above test where is action.execute() method invoked
    # the the daemon, for purposes of this test is possible to call it
    # directly this first call should be ok
    recvServerAction.execute(conf=conf,
                             caller=daemon,
                             logger=logger)
    # actual test: Executor will try to register another process with
    # the same id and fail ; it's the exception raised in Executor.execute()
    # (ExecutorException) which will translate into FDTDException
    try:
        try:
            recvServerAction.execute(conf=conf,
                                     caller=daemon,
                                     logger=logger)
            raise Exception("%s -- test not ok, expected exception "
                            "didn't occur" % testName)
        except FDTDException, ex:
            print "%s -- test ok, expected exception occur" % testName
    finally:
        print "%s -- test done, stopping" % testName
        # stopping the thread should also clean running processes associated
        # with daemon so the previously run FDT Java stuff,
        t.stop()
        logger.close()



def checkForProcesses(testName="somelogger", processName="java"):
    print ("%s -- checking for running '%s' "
           "processes ..."  % (testName, processName)) 
    os.system("ps axf | grep -i %s" % processName)
    print("%s -- end of check ####################################" %
           testName)
    

    
def raiseTimeoutException(self, *args):
    raise TimeoutException("Timeout exception.")



def waitUntilProcessFinished(pidFile, testName="<empty>"):
    """
    Check that no (previous) test process of the PID is 
    running - PID file can't exist in order to proceed with the next test.
    
    """
    counter = 0
    while 1:
        time.sleep(0.2)
        if os.path.exists(pidFile):
            counter += 1
            if counter == 10:
                c = open(pidFile, 'r').read()
                print ("%s -- file '%s' exists (content: '%s'), can't "
                       "continue the previous process may still be running, "
                       "waiting ..." % (testName, pidFile, c))
                counter = 0
        else:
            print ("%s -- the pidFile '%s' doesn't exist now, "
                   "continue" % (testName, pidFile))
            break
        
    
def main():
    """
    Perform various tests on FDTD daemon instance.
    Since there is a number of FDTD daemons binding ports in 
    quick consecution, they fail to bind this fast the same port,
    hence different ports are explicitly stated.

    At the end of these tests, there should not be any Java
    or Python related processes running, everything should be cleaned.
    
    """
    
    #checkForProcesses(processName = "java", testName = "initcheck")
    #checkForProcesses(processName = "python", testName = "initcheck")

    """
    errors / warnings at this test:
    There appear Pyro error traceback (from the test when daemon is run
    a thread), but doesn't seem to be harmful ...:
        Exception in thread Thread-1:
        Traceback (most recent call last):
          File "/usr/lib/python2.6/threading.py", line 525, in __bootstrap_inner
            self.run()
          File "fdtcplib/test/fdtd.py", line 273, in run
            self.fdtd.start()
          File "/home/xmax/tmp/caltech/phedex-fdt/fdtcp/fdtcplib/fdtd.py", line 307, in start
            self.pyroDaemon.requestLoop()
          File "/usr/local/lib/python2.6/dist-packages/Pyro/protocol.py", line 1068, in requestLoop
            self.handleRequests(timeout,others,callback)
          File "/usr/local/lib/python2.6/dist-packages/Pyro/protocol.py", line 1074, in handleRequests
            self._handleRequest_Threaded(timeout,others,callback)
          File "/usr/local/lib/python2.6/dist-packages/Pyro/protocol.py", line 1128, in _handleRequest_Threaded
            if self.sock in ins:
        AttributeError: 'Daemon' object has no attribute 'sock'
        
        or:
        
        Exception in thread Thread-1:
            Traceback (most recent call last):
              File "/usr/lib/python2.6/threading.py", line 525, in __bootstrap_inner
                self.run()
              File "fdtcplib/test/fdtd.py", line 270, in run
                self.fdtd.start()
              File "/home/xmax/tmp/caltech/phedex-fdt/fdtcp/fdtcplib/fdtd.py", line 307, in start
                self.pyroDaemon.requestLoop()
              File "/usr/local/lib/python2.6/dist-packages/Pyro/protocol.py", line 1068, in requestLoop
                self.handleRequests(timeout,others,callback)
              File "/usr/local/lib/python2.6/dist-packages/Pyro/protocol.py", line 1074, in handleRequests
                self._handleRequest_Threaded(timeout,others,callback)
              File "/usr/local/lib/python2.6/dist-packages/Pyro/protocol.py", line 1127, in _handleRequest_Threaded
                ins,outs,exs = safe_select(socklist,[],[],timeout)
              File "/usr/local/lib/python2.6/dist-packages/Pyro/protocol.py", line 1190, in safe_select
                return _selectfunction(r,w,e,timeout)
            error: (9, 'Bad file descriptor')
    """
    testName = "1-RegistTest"
    testFDTDExecutorDuplicateId(port=3000, testName=testName)
    time.sleep(0.5)
    #checkForProcesses(processName="java", testName=testName)
    

    # run tests which fails (since /tmp is a directory)
    # run without calling CleanupAction at the end (after failure)
    files = [TransferFile("/dev/zero", "/tmp")]
    testName = "2-FailedTestNoClean"
    testFDTD(files, port=4000, testName=testName, doCleanup=False)
    time.sleep(0.5)
    #checkForProcesses(processName="java", testName=testName)
    
    # test fails (since /tmp is a directory), but send CleanupAction
    # this time
    files = [TransferFile("/dev/zero", "/tmp")]
    testName = "3-FailedTestClean"
    testFDTD(files, port=5000, testName=testName, doCleanup=True)
    time.sleep(0.5)
    #checkForProcesses(processName="java", testName=testName)
        
    # run a transfer which doesn't fail
    # it has to be interrupted (simulate sinding ALARM signal
    # during progressing transfer), to make sure that killing and
    # cleaning of the running Java processes is done properly.
    # proper shutdown sequence of fdtd: ticket #22 - fdtd shutdown
    # sequence misfunctioning
    # test doen't fail (permissions ok, temp file is not created)
    # once the transfer is interrupted, CleanupAction is not sent by the
    # fdtcp client explicitly, fdtd is shutdown and has to clean properly
    # itself
    testName = "4-OKTransfer"
    files = [TransferFile("/dev/zero", "/dev/null")]
    testFDTD(files,
            port=6000,
            testName=testName,
            doCleanup=False,
            interrupt=True)
    time.sleep(0.5)
    #checkForProcesses(processName="java", testName=testName)
    
    # run a transfer which doesn't fail
    # ... as above, but with CleanupAction after interrupting
    testName = "5-OKTransferCleanup"
    files = [TransferFile("/dev/zero", "/dev/null")]
    testFDTD(files,
            port=7000,
            testName=testName,
            doCleanup=True,
            interrupt=True)
    time.sleep(0.5)
    #checkForProcesses(processName="java", testName=testName)
    #checkForProcesses(processName="python", testName=testName)
    
    # drive the whole transfer from fdtcp classes
    testName = "6-Combined"
    files = [TransferFile("/dev/zero", "/dev/null")]
    testfdtcpFdt(files, port=8000, testName=testName)
    checkForProcesses(processName="java", testName=testName)
    checkForProcesses(processName="python", testName=testName)
    
    # create pair of services (two different pid files, log files),
    # issue non failing transfer /dev/zero -> /dev/null ;
    # this will allow using more complete methods from fdtcp (e.g. whole
    # performCleanup since there should not be necessary any tricks with
    # transfer
    # IDs (this *-server, *-client) 
    # terminate the transfer at fdtcp by sending SIGHUP
    # #32 - fdtcp - signal handling implementation
    testName = "7-SigHandling"
    files = [TransferFile("/dev/zero", "/dev/null")]
    testFdtcpSignalHandling(files, (9000, 10000), testName=testName)    
    checkForProcesses(processName="java", testName=testName)
    checkForProcesses(processName="python", testName=testName)
    
    # test transfer is correct and will finish - transferring real data
    # fdtcp command will be
    #     SIGTERM killed - which shall immediately finish remote processes
    #     SIGKILL - no reaction possible - observe what happens at fdtd ends
    # remote fdtd services remain running
    # related to work on ticket #23 - Handle CleanupAction from fdtcp is
    # not triggered since it requires manual intervention
    # (final kill -15 <fdtdpid1, fdtdpid2>,
    #     this test will be normally commented out
    testName = "8-fdtcpKillSignal"
    print "%s -- not run, commented out" % testName 
    #testFdtcpKilledBySignalCorrectTransfers((11000, 12000)
    #   , testName = testName)
    #checkForProcesses(processName="java", testName=testName)
    #checkForProcesses(processName="python", testName=testName)
    
    # ticket #27 - fdtd - finish signal handler, distinguish shutdown,
    #   shutdown-forced
    testName = "9-ShutdownForced"
    files = [TransferFile("/dev/zero", "/dev/null")]
    testFdtdShutdownForced(files, (13000, 14000), testName=testName)
    checkForProcesses(processName="java", testName=testName)
    checkForProcesses(processName="python", testName=testName)
        
    
main()
