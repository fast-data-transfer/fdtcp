""" TODO """
import time
import Pyro4
from fdtcplib.common.actions import Action
from fdtcplib.common.actions import Result


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
            self.logger.debug("Executor %s has syncFlag set, wait until "
                         "it is unset ..." % exe)
            while True:
                time.sleep(0.3)
                if not exe.syncFlag:
                    break
                self.logger.debug("Executor %s has syncFlag still set, loop "
                                  "wait." % exe)
            self.logger.debug("Executor %s has syncFlag not set anymore, "
                              "continue." % exe)
        else:
            if exe:
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
        """ Returns hostname. TODO """
        raise NotImplementedError("Test action does not store Host information")

    def getMsg(self):
        """ Returns messages in queue. TODO """
        raise NotImplementedError("Test action does not store messages")

    def getLog(self):
        """ Returns log files. TODO """
        raise NotImplementedError("Test action does not store logs")
