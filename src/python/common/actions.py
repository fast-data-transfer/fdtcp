#!/usr/bin/env python2.7
"""
Classes holding details of communication transmitted between fdtcp and fdtd.

Implementations of actions - factual starting of FDT Java client/server
    processes by fdtd

Actions classes represent actions initiated from fdtcp, then shipped to
    remote party fdtd where some action instance settings are finalized
    and eventually performed.

Actions .execute() methods are called on the side of fdtd, so caller
    as well as the conf object are the one associated with the fdtd
    remote party and not with local fdtcp.
"""
from __future__ import division
from past.utils import old_div
import os
import time
import datetime
import psutil
import re

from fdtcplib.utils.Executor import Executor, ExecutorException
from fdtcplib.utils.utils import getHostName, getDateTime
from fdtcplib.utils.utils import getRandomString
from fdtcplib.common.errors import FDTDException, FDTCopyException


class CarrierBase(object):
    """
    Base class for all communication between fdtcp and FDTD service
    Base class for Actions, Result

    """

    def __init__(self, idc):
        self.id = idc

    def __str__(self):
        return self._debugDetails(self.__dict__)

    def _debugDetails(self, inputDict, indent=4):
        """ TODO doc """
        r = ""
        ind = ' ' * indent
        for k, v in list(list(inputDict.items())):
            if isinstance(v, dict):
                # do indent twice as much
                recurResult = self._debugDetails(v, indent=8)
                dictInfo = "'%s' (dict, %s items):\n" % (k, len(v))
                r = "".join([r, ind, dictInfo, recurResult])
            elif isinstance(v, list):
                listInfo = "'%s' (list, %s items):\n" % (k, len(v))
                r = "".join([r, ind, listInfo])
                for i in v:
                    # only compared to the list title
                    listInd = ind + ' ' * 4
                    r = listInd.join([r, "'%s'\n" % i])
            else:
                r = ind.join([r, "'%s': '%s'\n" % (k, v)])
        return r


class Action(CarrierBase):
    """
    Base class for all actions.
    timeout is client-side timeout to wait for the remote call. It's
    particularly useful when testing availability of the remote site,
    for we don't want to wail until a connection times out on firewall, etc.

    """

    def __init__(self, idA, timeout=None):
        CarrierBase.__init__(self, idA)
        self.timeout = timeout

    def execute(self):
        """ TODO doc """
        m = "Base class (abstract), no implementation execute()"
        raise NotImplementedError(m)


class TestAction(Action):
    """
    This action is used by client (fdtcp) to find out if
    daemon (fdtd service) is running and responding.
    This is the first communication between fdtcp and fdtd,
    id is generated here and used throughout the whole transfer process.
    Only timeout can be configurable for this type of action.
    """

    def __init__(self, srcHostName, dstHostName, timeout=None):
        idT = self._getId(srcHostName, dstHostName)
        Action.__init__(self, idT, timeout)

    def _getId(self, srcHostName, dstHostName):
        """
        Transfer job / request / id will consist of hostname of the
        machine fdtcp is invoked on and timestamp. This id will be used
        in all requests to fdtd for tracking the state of the transfer
        job, esp. by MonALISA ApMon.
        Transfers at fdtd will be associated with this ID - make it as
        unique as possible to avoid collisions.
        """
        h = getHostName()
        # u = getUserName()
        dt = getDateTime()
        r = getRandomString('a', 'z', 5)
        template = "fdtcp-%(host)s--%(source)s-to-%(dest)s--%(datetime)s-%(randomStr)s"
        d = dict(host=h, source=srcHostName, dest=dstHostName,
                 datetime=dt, randomStr=r)
        idT = template % d
        return idT

    def execute(self, **kwargs):
        del kwargs
        r = Result(self.id)
        r.status = 0
        return r


class ReceivingServerAction(Action):
    """ TODO doc """

    def __init__(self, idR, options):
        """
        Instance of this class is created by fdtcp and some parameters are
        passed (options), options is a dictionary.

        """
        Action.__init__(self, idR)
        self.options = options
        self.command = None

    def _setUp(self, conf, port):
        """ TODO doc """
        # separate method for testing purposes, basically sets up command
        self.options["sudouser"] = self.options["gridUserDest"]
        self.options["port"] = port
        self.options["monID"] = self.id
        newOptions = self.options
        if self.options['circuitClientIP'] and self.options['circuitServerIP']:
            newOptions['clientIP'] = self.options['circuitClientIP']
        self.command = conf.get("fdtReceivingServerCommand") % newOptions

    def _checkTargetFileNames(self, destFiles):
        """
        #36 - additional checks to debug AlreadyBeingCreatedException
        Check all the paths in the supplied list and log whether the files
        as well as the dotName form of the files exist.
        The intention is to help debug HDFS AlreadyBeingCreatedException
        """
        r = ""
        ind = ' ' * 4
        for f in destFiles:
            exists = os.path.exists(f)
            r = ind.join([r, "exists %5s: %s\n" % (exists, f)])
            dotName = '.' + os.path.basename(f)
            dotNameFull = os.path.join(os.path.dirname(f), dotName)
            exists = os.path.exists(dotNameFull)
            r = ind.join([r, "exists %5s: %s\n" % (exists, dotNameFull)])
        return r

    def _checkForAddressAlreadyInUseError(self, exMsg, port, logger):
        """
        Check if "Address already in use" error occurred and if so
        try to find out which process has the port.
        Problem #38
        """
        errMsg = "Address already in use"
        logger.debug("Checking for '%s' error message (port: %s) ... " %
                     (errMsg, port))
        addressUsedObj = re.compile(errMsg)
        match = addressUsedObj.search(exMsg)
        if not match:
            logger.debug("Error message '%s' not found, different failure.")
            return
        logger.debug("'%s' problem detected, analyzing running "
                     "processes ..." % errMsg)
        startTime = datetime.datetime.now()
        # TODO
        # netstat -tuap (pid is normally not available) so in this
        # special circumstance had to check connections of all running
        # processes .. not very elegant solution, shall be revised
        # once currently very rare #38 problem is understood
        found = False
        procs = psutil.pids()
        logger.debug("Going to check %s processes ..." % len(procs))
        for pid in procs:
            try:
                proc = psutil.Process(pid)
                conns = proc.connections()
            except psutil.AccessDenied:
                logger.debug("Access denied to process PID: %s, "
                             "continue ..." % pid)
                continue
            for conn in conns:
                # It can have multiple connections, so need to check all
                try:
                    connPort = int(conn[0].laddr[1])
                    if port == connPort:
                        m = ("Detected: process PID: %s occupies port: %s "
                             "(user: %s, cmdline: %s)" %
                             (pid, port, proc.username(), proc.cmdline()))
                        logger.debug(m)
                        found = True
                except AttributeError as er:
                    logger.debug("Got unnexpected attribute error. %s %s" % (conn[0], er))
                    continue
            if found:
                break
        endTime = datetime.datetime.now()
        elapsed = old_div(((endTime - startTime).microseconds), 1000)
        logger.debug("Process checking is over, took %s ms." % elapsed)

    def execute(self, conf=None, caller=None, apMon=None, logger=None):
        """
        This method is is called on the remote site where fdtd runs - here
        are also known all configuration details, thus final set up has to
        happen here.
        """
        startTime = datetime.datetime.now()
        # may fail with subset of FDTDException which will be propagated
        port = caller.getFreePort()
        self._setUp(conf, port)
        destFiles = self.options["destFiles"]
        logger.info("%s - checking presence of files at target "
                    "location ..." % self.__class__.__name__)
        logger.debug("Results:\n%s" % self._checkTargetFileNames(destFiles))
        user = self.options["sudouser"]
        logger.debug("Local grid user is '%s'" % user)
        toWaitFor = conf.get("fdtServerLogOutputToWaitFor") % dict(port=port)
        toWaitTimeout = conf.get("fdtServerLogOutputTimeout")
        killTimeout = conf.get("fdtReceivingServerKillTimeout")
        executor = Executor(self.id,
                            caller=caller,
                            command=self.command,
                            blocking=False,
                            port=port,
                            userName=user,
                            logOutputToWaitFor=toWaitFor,
                            killTimeout=killTimeout,
                            logOutputWaitTime=toWaitTimeout,
                            logger=logger)

        try:
            output = executor.execute()
        # on errors, do not do any cleanup or port releasing, from
        # Executor.execute() the instance is in the container and shall
        # be handled by CleanupProcessesAction
        except Exception as ex:
            m = ("Could not start FDT server on %s port: %s, reason: %s" %
                 (getHostName(), port, ex))
            logger.critical(m, traceBack=True)
            self._checkForAddressAlreadyInUseError(str(ex), port, logger)
            raise FDTDException(m)
        else:
            r = Result(self.id)
            r.status = 0
            # port on which FDT Java server runs
            r.serverPort = port
            r.msg = "FDT server is running"
            r.log = output
            logger.debug("Response to client: %s" % r)

            endTime = datetime.datetime.now()
            elapsed = (endTime - startTime).seconds
            par = dict(id=self.id, fdt_server_init=elapsed)
            logger.debug("Starting FDT server lasted: %s [s]." % elapsed)
            if apMon:
                logger.debug("Sending data to ApMon ...")
                apMon.sendParameters("fdtd_server_writer", None, par)
            return r


class AuthServiceAction(Action):
    """
    Client (fdtcp) will issue this action in order to obtain port on
    which AuthService runs, then fdtcp starts AuthClient to
    perform authentication.
    """

    def __init__(self, idA):
        Action.__init__(self, idA)

    def execute(self, conf=None, dummycaller=None, dummyapMon=None, logger=None):
        """
        This method is is called on the remote site where fdtd runs.
        """
        r = Result(self.id)
        r.status = 0
        # set the port on which AuthService runs
        r.serverPort = conf.get("portAuthService")
        logger.debug("Response to client: %s" % r)
        return r


class SendingClientAction(Action):
    """ TODO doc """

    def __init__(self, idS, options):
        """
        Instance of this class is created by fdtcp and some parameters are
        passed (options), options is a dictionary.
        """
        Action.__init__(self, idS)
        self.options = options
        self.command = None

    def _setUp(self, conf):
        """ TODO doc """
        # generate FDT fileList, put it into the same location as log file
        if conf.get("logFile"):
            logDir = os.path.dirname(conf.get("logFile"))
        else:
            logDir = "/tmp"
        directory = os.path.join(logDir, "fileLists")
        fileListName = os.path.join(directory, "fdt-fileList-%s" % self.id)
        try:
            if not os.path.exists(directory):
                os.mkdir(directory)
            fileList = open(fileListName, 'w')
        except IOError as ex:
            m = ("Could not create FDT client fileList file %s, "
                 "reason: %s" % (fileListName, ex))
            raise FDTDException(m)  # this will be propagated to fdtcp

        for f in self.options["transferFiles"]:
            # is list of TransferFiles instances
            fileList.write("%s\n" % f)
        fileList.close()
        self.options["fileList"] = fileListName
        self.options["monID"] = self.id
        newOptions = self.options
        if self.options['circuitClientIP'] and self.options['circuitServerIP']:
            newOptions['hostDest'] = self.options['circuitServerIP']

        self.command = conf.get("fdtSendingClientCommand") % newOptions

    def execute(self, conf=None, caller=None, dummyapMon=None, logger=None):
        """
        This method is invoked by fdtd once the action object is received
        from remote fdtcp (where the action instance was created). Options
        known on fdtd are set on the action instance (e.g. finalizing command
        for invoking FDT Java - location of fdt.jar is known only at fdtd site).
        """
        # this method is called on PYRO service side, user its logger
        # from now on
        localGridUser = self.options["gridUserSrc"]
        logger.debug("Local grid user is '%s'" % localGridUser)
        self.options["sudouser"] = localGridUser

        self._setUp(conf)
        killTimeout = conf.get("fdtSendingClientKillTimeout")
        executor = Executor(self.id,
                            self.command,
                            blocking=True,
                            caller=caller,
                            userName=localGridUser,
                            killTimeout=killTimeout,
                            syncFlag=True,
                            logger=logger)
        try:
            try:
                output = executor.execute()
            except ExecutorException as ex:
                m = ("FDT Java client on %s failed, "
                     "reason: %s" % (getHostName(), ex))
                logger.error(m)
                raise FDTDException(m)
            except Exception as ex:
                m = ("FDT Java client on %s failed, "
                     "reason: %s" % (getHostName(), ex))
                logger.error(m, traceBack=True)
                raise FDTDException(m)
            else:
                # no other exception was raised during execution
                r = Result(self.id)
                r.status = 0
                r.log = output
                r.msg = "Output from FDT client"
                logger.debug("FDT client log (as sent to "
                             "fdtcp):\n%s" % output)
                return r
        finally:
            # give signal on this actions Executor instance that its handling
            # finished (e.g. CleanupProcessesAction may be waiting for this)
            executor.syncFlag = False


class AuthClientAction(Action):
    """
    This action is run purely locally, everything happens from fdtcp.
    AuthClient (Java) store the remote username into a file
    (fileNameToStoreRemoteUserName) and execute method reads it in
    and forwards this remote Grid user name to local caller (fdtcp)
    and deletes the file.
    """

    def __init__(self, idA, options):
        Action.__init__(self, idA)
        self.options = options
        self.command = None

    def _setUp(self, conf, fileNameToStoreRemoteUserName):
        """ TODO doc """
        # separate method for testing purposes
        self.options["fileNameToStoreRemoteUserName"] = \
            fileNameToStoreRemoteUserName
        # conf is local configuration object, i.e. of local fdtcp
        self.options["x509userproxy"] = conf.get("x509userproxy")
        self.command = conf.get("authClientCommand") % self.options

    def execute(self, conf=None, dummycaller=None, dummyapMon=None, logger=None):
        """This method is invoked by fdtcp (locally)."""
        # fileNameToStoreRemoteUserName - file into which AuthClient
        # stores name of the Grid user at the remote party, this
        # information is then forwarded later to
        # fdtd which doens't have to do the user mapping lookup again
        fileName = "/tmp/" + self.id + "--" + getRandomString('a', 'z', 5)
        if os.path.exists(fileName):
            raise FDTCopyException("File %s exists." % fileName)

        self._setUp(conf, fileName)
        executor = Executor(self.id,
                            self.command,
                            blocking=True,
                            logger=logger)
        # here the Java AuthClient stores the Grid user name into the file
        output = executor.execute()

        try:
            remoteGridUser = open(fileName, 'r').read()
            os.remove(fileName)
        except Exception as ex:
            m = ("Problem handling file %s (reading remote Grid user "
                 "name), reason: %s" % (fileName, ex))
            raise FDTCopyException(m)

        # no exception was raised during execution (or handled well)
        r = Result(self.id)
        # TODO
        # this really reliable as authentication result?
        r.status = executor.returncode
        r.log = output
        return r, remoteGridUser


class CleanupProcessesAction(Action):
    """ TODO doc """

    def __init__(self, idC, timeout=None, waitTimeout=True):
        """
        id is mandatory - associated with previous actions.
        waitTimeout controls waiting for timeout interval before killing the
            command, waitTimeout = False means the cleanup will not wait and
            proceeds to kill immediately. See comments in FDTD.killProcess
            and further related to waitTimeout and
            #33 - CleanupProcessesAction - attribute to ignore any
                wait-to-finish timeouts
            waitTimeout has entirely different purpose from Action.timeout.

        """
        Action.__init__(self, idC, timeout)
        self.waitTimeout = waitTimeout

    def execute(self, dummyconf=None, caller=None, dummyapMon=None, logger=None):
        """
        all these parameters defined here and not at the
        constructor: execute()
        runs on when it is received at the remote end while the instance is
        created at the the client side - fdtcp.
        all these parameters are then associated with the fdtd side.

        """
        # get the executor instance whose process is going to be killed
        e = caller.getExecutor(self.id)
        caller.killProcess(self.id, logger, waitTimeout=self.waitTimeout)
        if e and e.syncFlag:
            logger.debug("Executor %s has syncFlag set, wait until "
                         "it is unset ..." % e)
            while True:
                time.sleep(0.3)
                if not e.syncFlag:
                    break
                logger.debug("Executor %s has syncFlag still set, loop "
                             "wait." % e)
            logger.debug("Executor %s has syncFlag not set anymore, "
                         "continue." % e)
        else:
            if e:
                logger.debug("Executor %s has syncFlag not set, "
                             "continue." % e)

        r = Result(self.id)
        r.status = 0
        r.msg = ("No errors caught during processing %s" %
                 self.__class__.__name__)
        return r


class Result(CarrierBase):
    """ TODO doc """

    def __init__(self, idR):
        """
        Result object always, id associated with previously
        launched action.

        """
        CarrierBase.__init__(self, idR)
        self.log = None
        self.msg = None
        self.status = None
        self.host = getHostName()
        self.serverPort = None

    def __str__(self):
        n = self.__class__.__name__
        r = ("%s: %s id: '%s' status: "
             "'%s' msg: '%s' " % (n, self.host, self.id, self.status,
                                  self.msg))
        return r
