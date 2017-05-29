"""

Classes holding details of communication transmitted between fdtcp and fdtd.

CleanupProcessesAction make a cleanup correct. Whenever transfer finishes or
fails with any exception, it should be called to clean up remaining processes.

"""
import time
import Pyro4
from fdtcplib.common.actions import Action
from fdtcplib.common.actions import Result
from fdtcplib.utils.utils import getHostName
from fdtcplib.common.errors import CleanupProcessException


@Pyro4.expose
class CleanupProcessesAction(Action):
    """ Clean Up process to clean all executors attached to that transfer request """

    def __init__(self, options):
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
        self.apMon = None
        self.id = options['transferId']
        Action.__init__(self, self.id)
        self.options = options
        self.status = -1
        self.logger = self.options['logger']
        self.caller = self.options['caller']
        self.conf = self.options['conf']
        self.lastMessage = ""
        if 'apmonObj' in self.options.keys():
            self.apMon = self.options['apmonObj']
        self.waitTimeout = True
        if 'waitTimeout' in self.options.keys():
            self.waitTimeout = self.options['waitTimeout']

    def execute(self):
        """
        all these parameters defined here and not at the
        constructor: execute()
        runs on when it is received at the remote end while the instance is
        created at the the client side - fdtcp.
        all these parameters are then associated with the fdtd side.

        """
        # get the executor instance whose process is going to be killed
        exe = self.caller.getExecutor(self.id)
        self.caller.killProcess(self.id, self.logger, waitTimeout=self.waitTimeout)
        if exe and exe.syncFlag:
            msg = "Executor %s has syncFlag set, wait until it is unset ..." % exe
            self.lastMessage = msg
            self.logger.debug(msg)
            while True:
                time.sleep(0.3)
                if not exe.syncFlag:
                    break
                msg = "Executor %s has syncFlag still set, loop wait." % exe
                self.lastMessage = msg
                self.logger.debug(msg)
            msg = "Executor %s has syncFlag not set anymore, continue." % exe
            self.lastMessage = msg
            self.logger.debug(msg)
        else:
            if exe:
                msg = "Executor %s has syncFlag not set, continue." % exe
                self.lastMessage = msg
                self.logger.debug("Executor %s has syncFlag not set, "
                                  "continue." % exe)

        rObj = Result(self.id)
        rObj.status = 0
        self.status = 0
        rObj.msg = ("No errors caught during processing %s" %
                    self.__class__.__name__)
        return rObj

    def getID(self):
        """ Returns transfer ID """
        return self.id

    def getStatus(self):
        """ Returns class status """
        return self.status

    def getHost(self):
        """ Returns hostname """
        return self.conf.get("hostname") or getHostName()

    def getMsg(self):
        """ Returns last raised message in the queue """
        return self.lastMessage

    def getLog(self):
        """ Returns log file lines """
        raise CleanupProcessException('CleanUp process does not have getLog method call.')

    def getServerPort(self):
        """Returns server port on which it is listening"""
        raise CleanupProcessException('CleanUp process does not have getServerPort method call.')

    def executeWithLogOut(self):
        """ Execute transfer which will log everything back to calling client """
        raise CleanupProcessException('CleanUp process does not have executeWithLogOut method call.')

    def executeWithOutLogOut(self):
        """ Execute without log output to the client on the fly. Logs can be received from getLog """
        raise CleanupProcessException('CleanUp process does not have executeWithOutLogOut method call.')
