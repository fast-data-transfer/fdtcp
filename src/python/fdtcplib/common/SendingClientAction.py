"""
Classes holding details of communication transmitted between fdtcp and fdtd.

Implementations of actions - factual starting of FDT Java client/server
    processes by fdtd

ReceivingServerAction starts FDT process for further communication.
SendingClientAction will connect to this FDT process and will transmit data.
"""
from __future__ import print_function
import os
import Pyro4
from fdtcplib.utils.Executor import Executor, ExecutorException
from fdtcplib.utils.utils import getHostName, getApmonObj
from fdtcplib.common.actions import Action
from fdtcplib.common.actions import Result
from fdtcplib.common.errors import FDTDException


@Pyro4.expose
class SendingClientAction(Action):
    """ Sending client class """

    def __init__(self, options):
        """
        Instance of this class is created by fdtcp and some parameters are
        passed (options), options is a dictionary.
        """
        self.apMon = None
        self.id = options['transferId']
        Action.__init__(self, self.id)
        self.options = options
        self.command = None
        self.status = -1
        self.logger = self.options['logger']
        self.caller = self.options['caller']
        self.conf = self.options['conf']
        self.executor = None
        self.port = None
        if 'apmonObj' in self.options.keys():
            self.apMon = self.options['apmonObj']

    def _setUp(self):
        """ Set up Sending client action """
        # generate FDT fileList, put it into the same location as log file
        if self.conf.get("logFile"):
            logDir = os.path.dirname(self.conf.get("logFile"))
        else:
            logDir = "/tmp"
        directory = os.path.join(logDir, "fileLists")
        fileListName = os.path.join(directory, "fdt-fileList-%s" % self.id)
        try:
            if not os.path.exists(directory):
                os.mkdir(directory)
        except IOError as ex:
            msg = ("Could not create FDT client fileList file %s, "
                   "reason: %s" % (fileListName, ex))
            self.status = -2
            raise FDTDException(msg)  # this will be propagated to fdtcp

        with open(fileListName, 'w') as fd:
            for fileName in self.options["transferFiles"]:
                # is list of TransferFiles instances
                fd.write("%s\n" % fileName)
        self.options["fileList"] = fileListName
        if 'monID' not in self.options:
            self.options["monID"] = self.id
        newOptions = self.options
        newOptions['apmonDest'] = self.conf.get("apMonDestinations")
        if not self.apMon:
            self.apMon = getApmonObj(newOptions['apmonDest'])

        self.command = self.conf.get("fdtSendingClientCommand") % newOptions

    def execute(self):
        """
        This method is invoked by fdtd once the action object is received
        from remote fdtcp (where the action instance was created). Options
        known on fdtd are set on the action instance (e.g. finalizing command
        for invoking FDT Java - location of fdt.jar is known only at fdtd site).
        """
        # this method is called on PYRO service side, user its logger
        # from now on
        localGridUser = self.options["gridUserSrc"]
        self.logger.debug("Local grid user is '%s'" % localGridUser)
        self.options["sudouser"] = localGridUser

        self._setUp()
        killTimeout = self.conf.get("fdtSendingClientKillTimeout")
        self.executor = Executor(self.id,
                                 self.command,
                                 caller=self.caller,
                                 userName=localGridUser,
                                 logger=self.logger)
        try:
            try:
                output = self.executor.execute()
            except ExecutorException as ex:
                msg = ("FDT Java client on %s failed, "
                       "reason: %s" % (getHostName(), ex))
                self.logger.error(msg)
                raise FDTDException(msg)
            except Exception as ex:
                msg = ("FDT Java client on %s failed, "
                       "reason: %s" % (getHostName(), ex))
                self.logger.error(msg, traceBack=True)
                raise FDTDException(msg)
            else:
                # no other exception was raised during execution
                rObj = Result(self.id)
                rObj.status = 0
                self.status = 0
                rObj.log = output
                rObj.msg = "Output from FDT client"
                self.logger.debug("FDT client log (as sent to "
                                  "fdtcp):\n%s" % output)
                return rObj
        finally:
            # give signal on this actions Executor instance that its handling
            # finished (e.g. CleanupProcessesAction may be waiting for this)
            self.executor.syncFlag = False

    def getID(self):
        """ Returns transfer ID """
        return self.id

    def getStatus(self):
        """ Returns class status """
        return self.status

    def getHost(self):
        """ Returns hostname. """
        return self.conf.get("hostname") or getHostName()

    def getMsg(self):
        """ Returns last raised message in the queue """
        return self.executor.lastMessage()

    def getLog(self):
        """ Returns log file lines """
        return self.executor.getLogs()

    def getServerPort(self):
        """Returns server port on which it is listening"""
        raise NotImplementedError("Sending client does not provide port info.")
        # This behaviour might change whenever we do pull mode.

    def executeWithLogOut(self):
        """ Execute transfer and yield log out to the client """
        for line in self.executor.executeWithLogOut():
            print(line, end='')
            yield line

    def executeWithOutLogOut(self):
        """ Execute without log output to the client on the fly. Logs can be received from getLog """
        return self.executor.executeWithOutLogOut()
