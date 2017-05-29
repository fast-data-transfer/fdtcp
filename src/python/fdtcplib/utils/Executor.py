"""
Component for running external commands.
Possibility to associate ID with the command (job) and username (running
processes under arbitrary usernames).

Handling standard output, standard error streams.
"""
from __future__ import print_function
import subprocess
import select
import logging
from fdtcplib.common.errors import ExecutorException
from fdtcplib.utils.Logger import Logger
from fdtcplib.utils.utils import debugDetails


class Executor(object):
    """
    Executing external process.
    """

    def __init__(self, idE, command, caller=None, port=None,
                 userName=None, logger=None):
        # id of the associated action / request
        self.id = idE
        # actual command to execute in the process
        self.command = command
        # caller is the creator of this Executor class instance, if caller is
        # provided, it has to have addExecutor(), removeExecutor() and
        # checkExecutorPresence() methods by which this instance
        # registers / de-registers itself with the upper layer (its invoker)
        self.caller = caller
        # in case of non-blocking process (and if it's a service running on
        # a port) keep track of this port, if desirable
        self.port = port
        # if the process is run via sudo, keep track of the sudo-owner of this
        # process (i.e. of this Executor) - needed when killing this process,
        # default None means the same user who runs the main script
        self.userName = userName

        self.logger = logger or Logger(name="Executor", level=logging.DEBUG)

        self.lastMessage = ""
        # process instance as created by subprocess.Popen
        self.proc = None
        # returncode from the underlying self.proc instance
        self.returncode = None

    def __str__(self):
        if self.proc:
            pid = self.proc.pid
        else:
            pid = "<unknown>"
        return "process PID: %s '%s' id:'%s'" % (pid, self.command, self.id)

    def getLogs(self):
        """ Gets all log lines from the log file which is assigned to the PID and
            same as transferID"""
        return ""
        # TODO. This has to be fixed now, as logs are pushed directly to client

    def executeWithOutLogOut(self):
        """ This will block and will wait until following subprocess finishes.
            There is no separation on debug and info and all messages will be returned."""
        msg = "Waiting for '%s' (PID: %s) to finish ..." % (self.command,
                                                            self.proc.pid)
        self.logger.info(msg)
        self.lastMessage = msg
        # waits here
        try:
            self.returncode = self.proc.wait()
        except OSError as ex:
            msg = "Waiting for process to complete failed (crashed/killed?), reason: %s" % ex
            self.logger.error(msg)
            self.lastMessage = msg
            self.returncode = str(ex)

        # process finished here, remove it from executors container
        # do not remove itself from executors, subsequent
        # CleanupProcessesAction may
        # be left out of context and this executor instance gets orphaned
        # if self.caller != None:
        #    self.caller.removeExecutor(self)
        # considered returncodes for a synchronous call
        if self.returncode == 0:
            msg = ("Command '%s' finished, no error raised, return code: "
                   "'%s'" % (self.command, self.returncode))
            # comment out now: e.g. in case of FDT Java client error, the
            # process output logs are logged 3 times. the only issue is
            # when fdtcp initiator crashes, there is nowhere to send logs then
            # the same comment applies below ...
            # self.logger.info(m) # log locally at fdtd side
            self.lastMessage = msg
            return msg
        else:
            msg = ("Command '%s' failed, return code: "
                   "'%s'" % (self.command, self.returncode))
            self.lastMessage = msg
            raise ExecutorException(msg)
        return

    def executeWithLogOut(self):
        """ execute and also push log back to the calling client.
            Separately it will return stdout and stderr. In case -v is used at
            client end, both messages will be printed."""
        while True:
            reads = [self.proc.stdout.fileno(), self.proc.stderr.fileno()]
            ret = select.select(reads, [], [])
            for fd in ret[0]:
                nextLine = ""
                if fd == self.proc.stdout.fileno():
                    nextLine = self.proc.stdout.readline()
                    self.logger.debug(nextLine)
                    yield {"STDOUT": nextLine}
                if fd == self.proc.stderr.fileno():
                    nextLine = self.proc.stderr.readline()
                    self.logger.debug(nextLine)
                    yield {"STDERR": nextLine}
            if self.proc.poll() is not None:
                break
        output = self.proc.communicate()[0]
        exitCode = self.proc.returncode
        if exitCode == 0:
            yield {"ReturnCode": exitCode, "Status": "SUCCESS"}
        else:
            yield {"ReturnCode": exitCode, "Status": "FAILED", "OUTPUT": output}

    def retlastMessage(self):
        """Returns last message which is stored for raising"""
        return self.lastMessage

    def execute(self):
        """ Prepare Executor. Client has to call either with log or without log."""
        self.logger.debug("Executing:\n%s" % debugDetails())

        # sanity check - if process of the current action id is not
        # already present in the caller's executor container
        # So this just simply means that users do not make mess with py-library.
        #
        if self.caller is not None:
            if self.caller.checkExecutorPresence(self):
                msg = ("There already is executor associated with request "
                       "id '%s' in the caller (FDTD) container! Duplicate "
                       "request? Something wasn't not cleared up properly?" %
                       self.id)
                self.lastMessage = msg
                raise ExecutorException(msg)

        # subprocess.Popen() requires arguments in a sequence, if run
        # with shell=True argument then could take the whole string
        try:
            self.proc = subprocess.Popen(self.command.split(), stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE, universal_newlines=True)
        except OSError as ex:
            # logs should be available
            logs = self.getLogs()
            msg = ("Command '%s' failed, reason: "
                   "%s\nlogs:\n%s" % (self.command, ex, logs))
            self.lastMessage = msg
            raise ExecutorException(msg)
        # register newly created process with the caller, even if it fails
        # so that subsequent CleanupProcesses action knows about it
        if self.caller is not None:
            self.caller.addExecutor(self)
