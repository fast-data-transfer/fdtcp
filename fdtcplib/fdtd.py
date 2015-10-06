#!/usr/bin/env python

"""
fdtcp project (aimed at integration of FDT and CMS PhEDEx)

https://twiki.cern.ch/twiki/bin/view/Main/PhEDExFDTIntegration
https://trac.hep.caltech.edu/trac/fdtcp

FDT service wrapper (FDT daemon - fdtd)
PYRO daemon
Invokes FDT Java client / server party

FDT Java instances are created as new processes rather than threads which
    can't be killed if necessary, e.g. when transfer hangs.

__author__ = Zdenek Maxa

"""


import os
import sys
sys.path.append("/usr/lib/python2.4/site-packages")
import re
import signal
import logging
import time
import threading
import datetime
import resource
from threading import Lock
try:
    # force loading fdtcplib.__init__.py (see comment in this file related
    # to PYRO_STORAGE env. variable setting) - must be before first
    # PYRO import
    import fdtcplib
    from ApMon import apmon
    from M2Crypto import SSL # just test dependencies
    from psutil import Process
    from psutil import NoSuchProcess
    import Pyro
    import Pyro.core
    from Pyro.errors import PyroError
    from fdtcplib.utils.Executor import Executor
    from fdtcplib.utils.Executor import ExecutorException
    from fdtcplib.utils.Config import Config
    from fdtcplib.utils.Logger import Logger
    from fdtcplib.utils.utils import getHostName
    from fdtcplib.utils.utils import getOpenFilesList
    from fdtcplib.common.actions import Result
    from fdtcplib.common.errors import ServiceShutdownBySignal
    from fdtcplib.common.errors import FDTDException
    from fdtcplib.common.errors import AuthServiceException
    from fdtcplib.common.errors import PortReservationException
    from fdtcplib.common.errors import TimeoutException
    from fdtcplib.utils.Config import ConfigurationException
    from fdtcplib.common.actions import CleanupProcessesAction
    from fdtcplib.common.actions import ReceivingServerAction
    from fdtcplib.common.actions import SendingClientAction  
except ImportError, ex:
    print "Can't import dependency modules: %s" % ex
    sys.exit(1)



class PortReservation(object):
    """
    Class holds information about reserving ports.
    Shall remove occurrences of Address already in use, etc
    See #38
    
    """
    
    def __init__(self, portMin, portMax):
        class Port(object):
            def __init__(self):
                self._port = 0
                self._reservedTimes = 0
                self._reservedNow = False
                        
        portRange = range(portMin, portMax + 1)
        self._ports = [Port() for i in range(len(portRange))]
        for port, pr in zip(self._ports, portRange):
            port._port = pr
        # just a counter of taken port
        self._numTakenPorts = 0
        # will be secured by lock, mutex access to port
        # reservation / releasing
        self._lock = threading.Lock()
        
        
    def reserve(self):
        """
        Reserve works on round-robin, so that the oldest released port will
        be re-used (shall prevent any 'already in use' error, 'could not
        bind ...' problems since the timeouts shall be well over given
        decent number of possible ports).
        
        """
        if len(self._ports) == self._numTakenPorts:
            raise PortReservationException("No free port to reserve. "
                                           "%s ports taken." %
                                           self._numTakenPorts)
        self._lock.acquire(True) # block
        candid = self._ports[0]
        for port in self._ports:
            if (not port._reservedNow and 
                port._reservedTimes < candid._reservedTimes):
                candid = port
                break
        else:
            # no other port was assigned, take the first one
            candid = self._ports[0]
        self._numTakenPorts += 1
        candid._reservedTimes += 1
        candid._reservedNow = True
        self._lock.release()
        return candid._port
    
    
    def release(self, portToRel):
        """
        Release currently occupied port.

        """
        m = ("Trying to release a port which is not currently "
             "reserved (%s)." % portToRel)
        self._lock.acquire(True) # block
        try:
            for port in self._ports:
                if port._port == portToRel:
                    if not port._reservedNow:
                        raise PortReservationException(m)
                    port._reservedNow = False
                    self._numTakenPorts -= 1
                    break
            else:
                raise PortReservationException(m)
        finally:
            self._lock.release()

    

class FDTDService(Pyro.core.ObjBase):
    """
    PYRO service invoked remotely (PYRO daemon)
    Have only very simplistic class - it's exposed to calls from network.

    """

    def __init__(self, logger, conf, apMon, fdtd):
        """
        Service / daemon has to have reference to the FDT daemon
        object (fdtd) because of administrative actions such as
        clean up of running processes initiated by the remote
        fdtcp client.

        """
        # this logger is the main daemon (fdtd) logger, if configured
        # each transfer request (which consists of multiple sub-request
        # (network calls)) can be logged into a separate file
        self.logger = logger
        self.conf = conf
        self.apMon = apMon
        self.fdtd = fdtd
        Pyro.core.ObjBase.__init__(self)
        self._stopFlag = False

    
    def _handleServiceStopped(self):
        m = "%s stopped or is being shutdown ..." % self.__class__.__name__
        self.logger.error(m)
        raise PyroError(m)
    

    def _getSeparateLogger(self, action):
        """
        Check if there already is an associated logger on a possibly
        running executor, used that one (do not re-initialize)

        """
        executor = self.fdtd.getExecutor(action.id)
        if executor:
            logger = executor.logger
        else:
            # reinitialize the logger                
            # log either into the location of the main log or into /tmp
            if self.conf.get("logFile"):
                logDir = os.path.dirname(self.conf.get("logFile"))
            else:
                logDir = "/tmp"
            logFileName = os.path.join(logDir, "transfer-%s.log" % action.id)
            logFile = oldLogFile = logFileName
            logger = Logger(name="transfer",
                            logFile=logFile,
                            level=self.conf.get("debug"))
        return logger

    
    def service(self, action):
        m = ("Request received: %s %s\n%s" %
             (20 * '-', action.__class__.__name__, action))
        self.logger.debug(m)
        numFiles, filesStr = getOpenFilesList()
        self.logger.debug("Logging open files: %s items:\n%s" %
                          (numFiles, filesStr))
        # should use separate, transfer request related log files?
        # logs sub-calls belonging to the same transfer will be appended
        transferSeparateLogFile = self.conf.get("transferSeparateLogFile")
        if transferSeparateLogFile:
            logger = self._getSeparateLogger(action)
            logger.debug(m)
            self.logger.debug("Logging separately into file %s" %
                              logger.logFile)
        else:
            # use the main logger
            logger = self.logger

        if self._stopFlag:
            self._handleServiceStopped()
        
        # this performs the request from the remote client
        try:
            result = action.execute(conf=self.conf,
                                    caller=self.fdtd,
                                    apMon=self.apMon,
                                    logger=logger)
            return result
        finally:
            m = ("End of request %s serving.\n%s\n\n\n" %
                 (action.__class__.__name__, 78 * '-'))
            if transferSeparateLogFile:
                # issue #24 - fdtd - logging into separate files fails on
                # failed transfer. problem was here - logger.close() closes
                # the logger when in case of a request which remains in
                # processing - ReceivingServerAction do not re-initialize
                # the logger if it's already open and close it
                # only after related CleanupProcessesAction
                # by implementing above, the bug
                # #41 - Too many open files (fdtd side) was
                # introduced - separate loggers should be closed except on
                # ReceivingServerAction and SendingClientAction, they will
                # be closed by associated CleanupProcessesAction
                # related issues: #41:comment:8
                logger.debug(m)
                if not isinstance(action, (ReceivingServerAction,
                                           SendingClientAction)):
                    logger.close()
            numFiles, filesStr = getOpenFilesList()
            self.logger.debug("Logging open files: %s items:\n%s" %
                              (numFiles, filesStr))
            self.logger.debug(m)
                        
    
    def setStop(self):
        """
        TODO: should be secured so that it is not called from outside ...
        
        """
        self._stopFlag = True        
        self.logger.debug("%s service stop flag set." %
                          self.__class__.__name__)



class FDTD(object):
    """
    FDTD - daemon object, wrapper object to PYRO services, keeps track
    of associated running processes.

    """
    _name = None
    
    def __init__(self, conf, apMon, logger):
        self._name = self.__class__.__name__        
        self.conf = conf
        self.apMon = apMon # MonALISA ApMon monitoring instance
        self.logger = logger
        self.logger.debug("Creating instance of %s ..." % self._name)

        # tracking ports occupied by already started FTD Java servers
        # ports are release once the FDT server finishes or is killed        
        try:
            portRangeStr = self.conf.get("portRangeFDTServer")
            portMin, portMax = [int(i) for i in portRangeStr.split(',')]
        except (ValueError, IndexError), ex:
            raise FDTDException("Incorrect format of port range definition: "
                                "'%s', reason: %s" % (portRangeStr, ex))
        # range of all possible ports reserved for FDT Java
        self._portMgmt = PortReservation(portMin, portMax)
        
        # dictionary of currently running processes spawned from the
        # PYRO service used to query status, clean up (terminate, kill)
        # when shutting down, key is id of the ExecutorAction, this
        # dictionary needs exclusive access
        self._executors = {}
        self._executorsLock = Lock()
        
        try:
            port = int(self.conf.get("port"))
        except (ValueError, TypeError), ex:
            raise FDTDException("Can't start %s, wrong port, reason: %s" %
                                (self._name, ex))
                
        host = self.conf.get("hostname") or getHostName()
        
        # multiple signals may be used later for stop, stop-force, etc
        signal.signal(signal.SIGHUP, self._signalHandler)
        signal.signal(signal.SIGTERM, self._signalHandler)
        signal.signal(signal.SIGUSR1, self._signalHandler)
        signal.signal(signal.SIGALRM, self._signalHandler) 
        
        self._initPYRO(host, port)
        self.service = FDTDService(self.logger, self.conf, self.apMon, self)
        
        self.logger.info("%s daemon object initialised." % self._name)

        
    def _initPYRO(self, host, port):
        """
        Initialise the PYRO service, start PYRO daemon.
        Insist on exactly this port for the service.
        
        """
        Pyro.core.initServer()
        self.logger.debug("Trying to bind to '%s:%s' ..." % (host, port))
        try:
            # insist on exactly this port
            self.pyroDaemon = Pyro.core.Daemon(host=host,
                                               port=port,
                                               norange=1)
        except PyroError, ex:
            m = ("PYRO service could not start (port:%s), reason: %s" %
                 (port, ex))
            raise FDTDException(m)
        
        self.logger.info("PYRO service is running on %s:%s" %
                         (self.pyroDaemon.hostname, self.pyroDaemon.port))
    
        
    def getFreePort(self):
        """
        Reserve a free port in a synchronized fashion.
        
        """
        port = self._portMgmt.reserve()
        self.logger.debug("Port '%s' is now reserved." % port)
        return port


    def releasePort(self, port):
        """
        Release a port in a synchronized fashion.
        
        """
        self._portMgmt.release(port)
        self.logger.debug("Port '%s' released." % port)
        

    def checkExecutorPresence(self, executor):
        """
        Return True of executor.id is already registered in the
        _executors container, False otherwise.
        
        """
        if executor.id in self._executors:
            return True
        else:
            return False
        

    def addExecutor(self, executor):
        # when logging, use the request-associated logger, not this
        # instance's one
        if self.checkExecutorPresence(executor):
            # there another check for this in Executor.execute() so this
            # shall never happen, at least when Executor is always used
            m = ("There already is executor associated with request "
                 "id '%s' in FDTD container! Duplicate request? Something "
                 "wasn't not cleared up properly?" % executor.id)
            raise FDTDException(m)
        else:
            self._executorsLock.acquire(True)
            self._executors[executor.id] = executor
            total = len(self._executors)
            self._executorsLock.release()
            executor.logger.debug("%s added to the FDTD executors container "
                                  "(total %s items)." % (executor, total))
                        
            
    def removeExecutor(self, e):
        """
        Removes Executor instance e from the _executors container when it's
        sure the associated process finished. Also free the port.
        For logging use the request-associated logger, not this
        instance's one
        
        """
        self._executorsLock.acquire(True)
        total = len(self._executors)
        e.logger.debug("FDT executors container before removing attempt "
                       "(total %s items)." % total)
        try:
            del self._executors[e.id]
            process = Process(e.proc.pid)
            e.logger.critical("Process of executor id '%s' (process "
                              "PID: %s) still exists! Not removing from "
                              "FDTD executors container." %
                              (e.id, e.proc.pid))
            # put it back
            self._executors[e.id] = e
        except KeyError:
            e.logger.error("Executor id '%s' not present in the FDTD "
                           "executors container." % e.id)
        except NoSuchProcess:
            e.logger.debug("Process doesn't exist now, ok (PID: %s, %s)." %
                           (e.proc.pid, e.id))
            if e.port:
                try:
                    self.releasePort(e.port)
                except PortReservationException, exx:
                    m = "Port release failed, reason: %s" % exx
                    if e.logger is not self.logger:
                        self.logger.critical(m)
                    e.logger.critical(m)
                else:
                    e.logger.debug("Port '%s' should be released." % e.port)
            else:
                e.logger.debug("Port property is not set, nothing to "
                               "release.")
            total = len(self._executors)
            e.logger.debug("%s removed from the FDTD executors container "
                           "(total %s items)." % (e, total))
        self._executorsLock.release()

        
    def getExecutor(self, id):
        """
        Returns executor reference from the executors container based on
        the given id (id of the transfer is the same as of the executor)
        and if it doesn't exist, return None.
        
        """
        self._executorsLock.acquire(True)
        try:
            r = self._executors[id]
        except KeyError:
            r = None
        self._executorsLock.release()
        return r
        
    
    def killProcess(self, id, logger, waitTimeout = True):
        """
        id is a key into self._executors pool
        waitTimeout - if set, killTimeout associated with the
            Executor instance is taken into account, ignored otherwise.
        
        """
        logger.debug("Processing clean up / process kill request for "
                     "transfer id '%s' ..." % id)
        if id in self._executors:
            executor = self._executors[id]
            m = self._killProcess(executor, logger, waitTimeout=waitTimeout)
            logger.info(m)
            self.removeExecutor(executor)
        else:
            m = ("No such process/action id '%s' in executors "
                 "containers." % id)
            logger.error(m)
        return m
        

    def start(self):
        objServiceName = self.service.__class__.__name__
        uri = self.pyroDaemon.connect(self.service, objServiceName)
        self.logger.info("%s waiting for requests ... ('%s' uri: '%s')" %
                         (self._name, objServiceName, uri))
        # the flow stops at this call - can be interrupted by a signal
        # (and handler is called) when running as a proper daemon in production
        # or from Keyboard (development mode)
        self.pyroDaemon.requestLoop()


    def _killProcess(self, executor, logger, waitTimeout=True):
        """
        Method to perform cleaning up / killing of running processes.
        If the process runs, check process's killTimeout, wait that time
        if it finishes, if not kill it.
        The issues is e.g. FDT Java server may still be flushing its buffers.

        waitTimeout - if set, killTimeout associated with the
            Executor instance is taken into account, ignored otherwise. 
        
        The logger variable may either be associated with a separate PYRO
        received request, i.e. associated with CleanupProcessesAction or if
        this method is called from within this same class, it would
        be self.logger. The latter case is e.g. when _killProcess is called
        after fdtd received shutdown signal. If this causes issues,
        executor.logger can be considered.
           
        """        
        e = executor
        logger.debug("Going to poll state: %s ..." % e)

        # do this check if there is no timeout associated and
        # process has already finished
        if e.proc.poll() > -1:
            returnCode = e.proc.wait()
            m = ("Process PID: %s finished, returncode: '%s'\nlogs:\n%s" %
                 (e.proc.pid, returnCode, e.getLogs()))
            return m
        
        if e.killTimeout > 0 and waitTimeout:
            logger.debug("Going to wait timeout: %s [s], waitTimeout: %s" %
                         (e.killTimeout, waitTimeout))
            for counter in range(e.killTimeout):
                if e.proc.poll() > -1:
                    returnCode = e.proc.wait()
                    m = ("Process PID: %s finished, returncode: "
                         "'%s'\nlogs:\n%s" %
                         (e.proc.pid, returnCode, e.getLogs()))
                    return m
                else:
                    logger.debug("Process PID: %s still runs, waiting ..." %
                                 e.proc.pid)
                    time.sleep(1)
            else:
                # waiting period exhausted
                logger.warn("Process PID: %s still has not finished "
                            "(timeout: %s [s]), going to kill it ..." %
                            (e.proc.pid, e.killTimeout))
        else:
            logger.warn("Going to kill process PID: %s, kill wait timeout: "
                        "%s [s] waitTimeout: %s ..." %
                        (e.proc.pid, e.killTimeout, waitTimeout))
            
        # python 2.4.3 Popen object has no attribute kill - can't do
        # executor.proc.kill() have to kill via external kill OS command
        try:
            # TODO
            # SIGTERM doesn't stop properly all client threads in
            # AuthService GSIBaseServer, have to use brute force SIGKILL
            if e.userName:
                opt = dict(pid=e.proc.pid, sudouser=e.userName)
                command = self.conf.get("killCommandSudo") % opt
            else:
                opt = dict(pid=e.proc.pid)
                command = self.conf.get("killCommand") % opt

            killExec = Executor(e.id,
                                command,
                                blocking=True,
                                logger=logger)
            output = killExec.execute()
        except ExecutorException, ex:
            m = ("Error when killing process PID: %s (kill process: %s), "
                 "reason: %s\nlogs from the killed-attempt process:\n%s" %
                 (e.proc.pid, killExec, ex, e.getLogs()))
            # will be logged locally with the fdtd daemon
            logger.error(m)
            # will be propagated and logged with remote fdtcp client
            raise FDTDException(m)
        else:
            logs = e.getLogs()
            # it was observed that sometimes 
            # OSError [Errno 10] No child processes
            # is raised here, probably when the process already finished?
            # # check #8 description
            try:
                code = e.proc.wait()
            except OSError, ex:
                logger.error("Could not retrieve the returncode, "
                             "reason: %s" % ex)
                code = "unknown: %s" % ex
            m = "%s killed, returncode: '%s'\nlogs:\n%s" % (e, code, logs)
            logger.debug("Checking that process was killed ...")
            try:
                p = Process(e.proc.pid)
            except NoSuchProcess, ex:
                logger.debug("Process PID: %s doesn't exist now." %
                             e.proc.pid)
            else:
                logger.error("Process PID: %s still exists ('%s')." % p)
            return m
            
    
    def shutdown(self):
        """
        Shutdown sequence of the fdtd daemon.
        Cleaning all running processes (FDT Java).
        
        """
        self.logger.warn("Shutting down %s ..." % self._name)
        
        # do this as soon as possible, before PYRO daemon goes down so that
        # clients connected beyond this point are notified by
        # PyroError in response
        self.service.setStop()
        
        self.pyroDaemon.shutdown(True)
        self.logger.warn("PYRO internal daemon shutdown flag set.")
        
        self.logger.warn("%s associated processes running." %
                         len(self._executors))
        self._executorsLock.acquire()
        loggersToClose = []
        try:
            for id in self._executors:
                # here calling ._killProcess with the FDTD instance logger
                # this operation is not related to any request
                m = self._killProcess(self._executors[id],
                                      self.logger,
                                      waitTimeout=False)
                self.logger.info(m)
                # check for separate log files, if it's open, close
                e = self._executors[id]
                if (e.logger is not self.logger) and e.logger.isOpen:
                    loggersToClose.append(e.logger)
        except FDTDException, ex:
            self.logger.error(ex)
        self._executorsLock.release()
        
        """
        Calling pyroDaemon.closedown() is troublesome and in fact not clear
        if necessary at all, unlike pyroDaemon.shutdown()
        It seems that it didn't matter calling closedown() before or after
        stopping FDT Java processes which, in the case of client action
        which is blocking, were attached to a hanging PYRO call.
        See Ticket #22 - fdtd shutdown sequence misfunctioning for details
        Interestingly, preventing hanging via signal/alarm also not always
        reliably worked.
        Leave comment out for reference.
        self.logger.warn("Going to call pyroDaemon.closedown() ...")
        try:
            signal.alarm(3) # raise alarm in timeout seconds
            self.pyroDaemon.closedown()
            self.logger.warn("pyroDaemon.closedown() call successful.")
        except TimeoutException:
            self.logger.error("pyroDaemon.closedown() hanging, continue "
                              "forced. End of shutdown sequence.")
        else:
            self.logger.warn("%s stopped, whole shutdown sequence "
                             "successful." % self._name)
        """
        self._checkDaemonReleasedPort()
        # if there were any executors with their own dedicated separated
        # log files, these shall be closed now
        for l in loggersToClose:
            if l.isOpen():
                l.warn("Service is being shutdown, closing executor open "
                       "log file '%s'" % l.myLogFile)
                l.close()
        self.logger.warn("%s stopped, whole shutdown sequence "
                         "successful." % self._name)
        
        
    def _checkDaemonReleasedPort(self):
        """
        Method periodically checks that the port of the daemon is released.
        It's useful esp. when running tests which are binding the same
        port or when restarting the service.
        
        """
        port = self.conf.get("port")
        port = int(port)
        pid = os.getpid()
        self.logger.debug("Going to check that FDTD daemon (PID: %s) "
                          "released its port %s ..." % (pid, port))
        process = Process(pid)
        stillBound = True
        while stillBound:
            # connection(fd=115, family=2, type=1,
            #       local_address=('10.0.0.1', 48776),
            #       remote_address=('93.186.135.91', 80),
            #       status='ESTABLISHED')
            conns = process.get_connections()
            for conn in conns:
                la = conn.local_address
                self.logger.debug("FDTD daemon connections: '%s'" %
                                  str(conn))
                if la[1] == port:
                    self.logger.debug("\tnot yet released, waiting ...")
                    time.sleep(0.2)
                    continue
            else:
                # exhausted all connections (if any), port must be
                # released now
                self.logger.debug("FDTD daemon released port %s." % port)
                stillBound = False
                
            
    def _signalHandler(self, signum, frame):
        if signum == signal.SIGALRM:
            self.logger.warn("SIGALRM signal %s caught, raising "
                             "exception." % signum)
            raise TimeoutException("Timeout exception.")
        if signum == signal.SIGHUP:
            # SIGHUP: the service goes down only if there is no transfer
            # in progress
            self.logger.warn("SIGHUP signal %s caught, checking for running "
                             "transfer(s) ..." % signum)
            self._executorsLock.acquire(True)
            execCounter = 0
            for e in self._executors.values():
                if e.id == "AuthService":
                    continue # AuthService is present all the time, ignore
                else:
                    # other executor IDs - transfer - do not shutdown then
                    self.logger.debug("In executors container: %s" % e)
                    execCounter += 1
            self._executorsLock.release()
            self.logger.debug("Signal handler: %s transfers running." %
                              execCounter)
            numFiles, filesStr = getOpenFilesList()
            self.logger.debug("Signal handler: open files: %s items:\n%s" %
                              (numFiles, filesStr))
            if execCounter == 0:
                m = ("SIGHUP signal %s - no transfer(s) in progress, "
                     "shutdown." % signum)
                raise ServiceShutdownBySignal(m)
            else:
                self.logger.warn("SIGHUP signal %s - transfer(s) in "
                                 "progress, ignored." % signum)
        if signum == signal.SIGTERM:
            numFiles, filesStr = getOpenFilesList()
            self.logger.debug("Signal handler: open files: %s "
                              "items:\n%s" % (numFiles, filesStr))
            m = ("SIGTERM signal %s caught, shutting down "
                 "(forced) ..." % signum)
            # raise exception rather than calling .shutdown() directly,
            # this way it can be only shutdown from one place
            raise ServiceShutdownBySignal(m)



class ConfigFDTD(Config):
    """
    Class holding various options and settings which are either predefined
    in the configuration file, overriding from command line options is
    considered.

    """

    # mandatory configuration values, integers
    _mandatoryInt = ["port",
                     "portAuthService",
                     "fdtSendingClientKillTimeout",
                     "fdtServerLogOutputTimeout",
                     "fdtReceivingServerKillTimeout",
                     "authServiceLogOutputTimeout"]
    # mandatory configuration values, strings
    _mandatoryStr = ["fdtSendingClientCommand",
                     "fdtReceivingServerCommand",
                     "debug",
                     "portRangeFDTServer",
                     "transferSeparateLogFile",
                     "fdtServerLogOutputToWaitFor",
                     "authServiceLogOutputToWaitFor",
                     "authServiceCommand",
                     "killCommandSudo",
                     "killCommand",
                     "daemonize"]

    def __init__(self, args):
        # 1 - shall point to the same directory
        currDir = os.path.abspath(__file__).rsplit(os.sep, 1)[0]
        currDirConfig = os.path.join(currDir, "fdtd.conf")
        # consider only config file being in the same directory
        # as well as in the system config directory location
        locations = [currDirConfig, "/etc/fdtcp/fdtd.conf"]
        self.usage = None
        Config.__init__(self, args, locations)


    def processCommandLineOptions(self, args):
        """
        This method gets called from base class.
        
        """
        help = "debug output level, for possible values see the config file"
        self._parser.add_option("-d", "--debug", help=help)
        help = "port number on which to start local fdtd service"
        self._parser.add_option("-p", "--port", help=help)
        help = "configuration file for fdtd service"
        self._parser.add_option("-c", "--config", help=help)
        help = "print this help"
        self._parser.add_option("-h", "--help", help=help, action='help')
        help = "specify hostname of this machine"
        self._parser.add_option("-H", "--hostname", help=help)
        help = "output log file"
        self._parser.add_option("-l", "--logFile", help=help)
        help = "run the service on the background as daemon process"
        self._parser.add_option("-a",
                                "--daemonize",
                                action="store_true",
                                help=help)
        help = ("file to store PID of the daemon process (when running "
                "with daemonize)")
        self._parser.add_option("-i", "--pidFile", help=help)
        help = ("each transfer related requests will be logged in a "
                "separate log file")
        self._parser.add_option("-s",
                                "--transferSeparateLogFile",
                                action="store_true", help=help)

        # opts - new processed options, items defined above as attributes
        # args - remainder of the input array
        opts, args = self._parser.parse_args(args=args)
        
        # want to have _options a dictionary, rather than instance
        # some Values class from within optparse.OptionParser
        #self._options = opts
        self._options = {}
        self._options = eval(str(opts))
        


class AuthService(object):
    """
    Class for encapsulating process of AuthService - Grid authentication
    service - runs in a single instance per fdtd
    Shutdown of the process is taken care of by FDTD instance, once this
    process is started, it is registered with FDTD which will kill it
    when it goes down.

    """
    
    # TODO
    # may need to flush its buffers with output, though there should not
    # significant amount of data, but this would have to done either from
    # Java or something will have automatically poll this AuthService
    # executor ...
    
    def __init__(self, fdtd, conf, logger):
        self.fdtd = fdtd
        self.conf = conf
        self.logger = logger
        
        self.logger.debug("Creating instance of AuthService ...")
        self.options = {}
        self.options["port"] = self.conf.get("portAuthService")
        command = self.conf.get("authServiceCommand") % self.options
        toWaitFor = self.conf.get("authServiceLogOutputToWaitFor")
        timeout = self.conf.get("authServiceLogOutputTimeout")
        self.executor = Executor("AuthService",
                                 command=command,
                                 blocking=False,
                                 caller=self.fdtd,
                                 logOutputToWaitFor=toWaitFor,
                                 logOutputWaitTime=timeout,
                                 logger=self.logger)
        try:
            output = self.executor.execute()
            self.logger.debug(output)
        except ExecutorException, ex:
            m = "Could not start AuthService, reason: %s" % ex
            raise AuthServiceException(m)



def daemonize(conf, logger):
    """
    Store pid of the current process into pidFile and fork the daemon
    process (FDTD).
    Daemonization recipe compiled from several sources and compared to
    a number of recipes available on the internet.
    
    """
    logger.info("Preparing for daemonization (parent process "
                "PID: %s) ..." % os.getpid())
    
    # check that there is a log defined, otherwise fail - need to
    # redirect stdout, stderr stream into this file
    if not logger.logFile:
        logger.fatal("No log file defined, necessary when running as "
                     "daemon, exit.")
        logger.close()
        sys.exit(1)
    # check if there is pidFile defined - necessary in daemon mode
    if not conf.get("pidFile"):
        logger.fatal("No pid file defined, necessary when running as "
                     "daemon, exit.")
        logger.close()
        sys.exit(1)
    
    pidFile = conf.get("pidFile")
    # try opening the file for append - if exists - fail: fdtd.py might
    # be running or the file was left behind
    if os.path.isfile(pidFile):
        logger.fatal("File '%s' exists, can't start, remove it first." %
                     pidFile)
        logger.close()
        sys.exit(1)
        
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
        # exit parent code
        sys.exit(0)
    
    # decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(0)
    # don't change current working directory (os.chdir("/"))

    # fork again so we are not a session leader
    if os.fork() != 0:
        sys.exit(0)

    # output streams redirection into the log file
    # log file is already used by logger, concurrent writes may
    # get messy ... ideally there however should not be any logging
    # into streams from now on ...
    numFiles, filesStr = getOpenFilesList()
    logger.debug("Logging open files: %s items:\n%s" % (numFiles, filesStr))
    logger.debug("The process is daemonized, redirecting "
                 "stdout, stderr, stdin descriptors ...")
    for f in sys.stdout, sys.stderr:
         f.flush()
    logFile = file(logger.logFile, "a+", 0) # buffering - 0 (False)
    devNull = file("/dev/null", 'r')
    os.dup2(logFile.fileno(), sys.stdout.fileno())
    os.dup2(logFile.fileno(), sys.stderr.fileno())
    os.dup2(devNull.fileno(), sys.stdin.fileno())
    
    logger.debug("Redirecting streams is over.")
    numFiles, filesStr = getOpenFilesList()
    logger.debug("Logging open files: %s items:\n%s" % (numFiles, filesStr))
    
    # finally - the daemon process code, first store it's PID into file
    pid = os.getpid()
    logger.info("Running as daemon process: PID: %s (forked), "
                "PID file: '%s'" % (pid, pidFile))
    pidFileDesc = open(pidFile, 'w')
    pidFileDesc.write(str(pid))
    pidFileDesc.close()
    
    logger.debug("End of daemonization.")
    

def startApplication(conf, logger):
    """
    Main daemon function.
    
    Issues with moving ApMon initialization around:
        - if here, there is init msg which doesn't appear now for the
          streams were closed in daemonize()
        - moving before the streams were closed (i.e. moving to main())
          caused issues when calling apMon.free() - the flow stopped
          thre for unknown reason yet no exception was raised.
        Leave ApMon like this, as is!

    """
    apMon = None
    apMonDestConf = conf.get("apMonDestinations")
    if apMonDestConf:
        apMonDestinations = tuple(apMonDestConf.split(','))
        logger.info("Initializing MonALISA ApMon, "
                    "destinations: %s ..." % (apMonDestinations,))
        apMon = apmon.ApMon(apMonDestinations)
        apMon.enableBgMonitoring(True)
    else:
        logger.info("MonALISA ApMon is not enabled, no "
                    "destinations provided.")
    
    # use DNS names rather than IP address
    Pyro.config.PYRO_DNS_URI = True
    
    daemon = None
    try:
        try:
            daemon = FDTD(conf, apMon, logger)
            authService = AuthService(daemon, conf, logger)
            daemon.start()
        except AuthServiceException, ex:
            logger.fatal("Exception during AuthService startup, "
                         "reason: %s" % ex)
        except (FDTDException, ), ex:
            logger.fatal("Exception during FDTD initialization, "
                         "reason: %s" % ex)
        except KeyboardInterrupt:
            logger.fatal("Interrupted from keyboard ...")
        except ServiceShutdownBySignal, ex:
            logger.fatal(ex)
        except Exception, ex:
            logger.fatal("Exception was caught ('%s'), reason: %s" %
                         (ex.__class__.__name__, ex), traceBack=True)
    finally:
        if daemon:
            try:
                daemon.shutdown()
            except Exception, exx:
                logger.fatal("Exception occurred during shutdown sequence, "
                             "reason: %s" % exx, traceBack=True)
        try:
            if apMon:
                logger.debug("Releasing ApMon ...")
                apMon.free()
            
            # if daemonize, pidFile should have been created,
            # delete it now when shutting down
            if conf.get("daemonize"):
                pidFile = conf.get("pidFile")
                logger.info("Deleting the PID file '%s' ... " % pidFile)
                try:
                    os.remove(pidFile)
                    logger.debug("File '%s' removed." % pidFile)
                except OSError, ex:
                    logger.error("Could not remove PID file '%s', "
                                 "reason: %s" % (pidFile, ex))
        except Exception, exx:
            logger.fatal("Exception occurred during shutdown-cleanup, "
                         "reason: %s" % exx, traceBack=True)
        logger.close()

      
def main():
    # all values and action information held in the conf object
    optBackup = sys.argv[:]
    try:
        conf = ConfigFDTD(sys.argv[1:])
        conf.sanitize()
    except ConfigurationException, ex:
        print "fdtd failed to start, reason: %s" % ex
        sys.exit(1)
            
    logger = Logger(name="fdtd",
                   logFile=conf.get("logFile"),
                   level=conf.get("debug"))
    # ticket #35 - mercurial expandable keywords in the code
    # information from the SCM (expandable keywords)
    versionInfo = dict(Revision="$Revision: 99536bb6d942 $",
                       Tags="$Tags: tip $")
    logger.info("fdtd starting ... version: %s" %
                logger.pprintFormat(versionInfo))
    logger.debug("Search sys.path:\n%s\n" % logger.pprintFormat(sys.path))
    logger.debug("PYRO_STORAGE: '%s'" % os.environ.get("PYRO_STORAGE"))
    numOpen = resource.getrlimit(resource.RLIMIT_NOFILE)
    logger.debug("Number of allowed open files: %s" % (numOpen,))
    
    logger.debug("Input command line arguments: '%s'" % optBackup)
    logger.debug("Configuration values (processed):\n%s\n" %
                  logger.pprintFormat(conf._options))
    
    # daemonization
    if conf.get("daemonize"):
        daemonize(conf, logger)
    else:
        logger.info("Starting the service on foreground ...")
        
    startApplication(conf, logger)

        

if __name__ == "__main__":
    main()
