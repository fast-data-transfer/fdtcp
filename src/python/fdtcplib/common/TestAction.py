""" TODO """
import Pyro4
from fdtcplib.common.actions import Action
from fdtcplib.common.actions import Result
from fdtcplib.utils.utils import getId


@Pyro4.expose
class TestAction(Action):
    """
    This action is used by client (fdtcp) to find out if
    daemon (fdtd service) is running and responding.
    This is the first communication between fdtcp and fdtd,
    id is generated here and used throughout the whole transfer process.
    Only timeout can be configurable for this type of action.
    """

    def __init__(self, options):
        self.idT = getId(options['hostSrc'], options['hostDest'])
        self.status = -1
        Action.__init__(self, self.idT, options['timeout'])

    def execute(self):
        """ Execute TestAction """
        rObj = Result(self.idT)
        rObj.status = 0
        self.status = rObj.status
        return rObj

    def getID(self):
        """ Returns transfer ID """
        return self.idT

    def getStatus(self):
        """ Returns class status """
        return self.status

    def getHost(self):
        """ Returns hostname """
        raise NotImplementedError("Test action does not store Host information")

    def getMsg(self):
        """ Returns messages in queue """
        raise NotImplementedError("Test action does not store messages")

    def getLog(self):
        """ Returns log files """
        raise NotImplementedError("Test action does not store logs")
