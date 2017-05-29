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
import os
from fdtcplib.utils.Executor import Executor
from fdtcplib.utils.utils import getHostName
from fdtcplib.utils.utils import getRandomString
from fdtcplib.common.errors import FDTCopyException


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
        """ return pretified debug details """
        out = ""
        ind = ' ' * indent
        for k, j in list(list(inputDict.items())):
            if isinstance(j, dict):
                # do indent twice as much
                recurResult = self._debugDetails(j, indent=8)
                dictInfo = "'%s' (dict, %s items):\n" % (k, len(j))
                out = "".join([out, ind, dictInfo, recurResult])
            elif isinstance(j, list):
                listInfo = "'%s' (list, %s items):\n" % (k, len(j))
                out = "".join([out, ind, listInfo])
                for i in j:
                    # only compared to the list title
                    listInd = ind + ' ' * 4
                    out = listInd.join([out, "'%s'\n" % i])
            else:
                out = ind.join([out, "'%s': '%s'\n" % (k, j)])
        return out


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
        """ Base class execute. This should be overseeded by super class """
        msg = "Base class (abstract), no implementation execute()"
        raise NotImplementedError(msg)

    def getID(self):
        """ Base class execute. This should be overseeded by super class """
        msg = "Base class (abstract), no implementation execute()"
        raise NotImplementedError(msg)


class AuthServiceAction(Action):
    """
    Client (fdtcp) will issue this action in order to obtain port on
    which AuthService runs, then fdtcp starts AuthClient to
    perform authentication.
    """

    def __init__(self, idA):
        self.id = idA
        self.status = -1
        Action.__init__(self, idA)

    def execute(self, conf=None, caller=None, apMon=None, logger=None):
        """
        This method is is called on the remote site where fdtd runs.
        """
        rObj = Result(self.id)
        rObj.status = 0
        self.status = 0
        # set the port on which AuthService runs
        rObj.serverPort = conf.get("portAuthService")
        logger.debug("Response to client: %s" % rObj)
        return rObj


class AuthClientAction(Action):
    """
    This action is run purely locally, everything happens from fdtcp.
    AuthClient (Java) store the remote username into a file
    (fileNameToStoreRemoteUserName) and execute method reads it in
    and forwards this remote Grid user name to local caller (fdtcp)
    and deletes the file.
    """
    # TODO. This has to be grid authentication to be more secure.
    def __init__(self, idA, options):
        self.id = idA
        Action.__init__(self, idA)
        self.options = options
        self.command = None

    def _setUp(self, conf, fileNameToStoreRemoteUserName):
        """ Setup authentication client action """
        # separate method for testing purposes
        self.options["fileNameToStoreRemoteUserName"] = \
            fileNameToStoreRemoteUserName
        # conf is local configuration object, i.e. of local fdtcp
        self.options["x509userproxy"] = conf.get("x509userproxy")
        self.command = conf.get("authClientCommand") % self.options

    def execute(self, conf=None, caller=None, apMon=None, logger=None):
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
            remoteGridUser = open(fileName, 'r').read()  # TODO close
            os.remove(fileName)
        except Exception as ex:
            msg = ("Problem handling file %s (reading remote Grid user "
                   "name), reason: %s" % (fileName, ex))
            raise FDTCopyException(msg)

        # no exception was raised during execution (or handled well)
        rObj = Result(self.id)
        rObj.status = executor.returncode
        rObj.log = output
        return rObj, remoteGridUser


class Result(CarrierBase):
    """ Result class to return nice message to all """

    def __init__(self, idR):
        """
        Result object always, id associated with previously
        launched action.

        """
        self.id = idR
        CarrierBase.__init__(self, idR)
        self.log = None
        self.msg = None
        self.status = None
        self.host = getHostName()
        self.serverPort = None

    def __str__(self):
        className = self.__class__.__name__
        msg = ("%s: %s id: '%s' status: "
               "'%s' msg: '%s' " % (className, self.host, self.id, self.status,
                                    self.msg))
        return msg
