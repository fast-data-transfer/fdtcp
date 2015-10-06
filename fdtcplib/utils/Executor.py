"""
Component for running external commands.
Possibility to associate ID with the command (job) and username (running
processes under arbitrary usernames).

Handling standard output, standard error streams.

__author__ = Zdenek Maxa

"""


import datetime
import os
import subprocess
import sys
import tempfile
import shutil
import time
import logging
import socket
import types

from fdtcplib.utils.Logger import Logger
from fdtcplib.utils.utils import getHostName



class ExecutorException(Exception):
    pass



class Executor(object):
    """
    Executing external process.
    
    """

    def __init__(self,
                 id,
                 command,
                 blocking=False,
                 caller=None,
                 catchLogs=True,
                 port=None,
                 userName=None,
                 logOutputToWaitFor=None,
                 logOutputWaitTime=0,
                 killTimeout=0,
                 syncFlag=False,
                 logger=None):
        # id of the associated action / request
        self.id = id
        # actual command to execute in the process
        self.command = command
        # boolean flag - blocking / non-blocking process, in case of blocking,
        # wait until the process finished
        self.blocking = blocking
        # caller is the creator of this Executor class instance, if caller is
        # provided, it has to have addExecutor(), removeExecutor() and
        # checkExecutorPresence() methods by which this instance
        # registers / de-registers itself with the upper layer (its invoker)
        self.caller = caller
        # whether or not to capture stdout, stderr logs
        self.catchLogs = catchLogs
        # in case of non-blocking process (and if it's a service running on
        # a port) keep track of this port, if desirable
        self.port = port
        # if the process is run via sudo, keep track of the sudo-owner of this
        # process (i.e. of this Executor) - needed when killing this process,
        # default None means the same user who runs the main script
        self.userName = userName
        # in case of non-blocking scenario, there is limited possibility to
        # make sure that the process has really started (there is no .wait()
        # used) and that it possibly bound a desired port - this attribute 
        # offers an opportunity to wait for certain known log output from the
        # process that is being started.
        # other possibilities are checking output of fuser, lsof, but
        # privileged permissions will have to provided in case processes are
        # run under arbitrary user accounts)
        self.logOutputToWaitFor = logOutputToWaitFor
        # in case of non-blocking process, wait this amount of time at
        # maximum for logOutputToWaitFor to come up before declaring the
        # process failed will be working with time differences and comparing
        # integers
        self.logOutputWaitTime = int(logOutputWaitTime) # [seconds]
        
        # when about to kill the process, it's killTimeout attribute is check
        # which defines timeout to wait before killing the process
        self.killTimeout = killTimeout
        
        # syncFlag is indicator that action associated with the Executor
        # instance has finished: e.g. CleanupProcessesAction shall finish
        # after killing SendingClientAction executor's until
        # SendingClientAction finished all its job before associated
        # CleanupProcessesAction finishes itself
        self.syncFlag = syncFlag
        
        self.logger = logger or Logger(name="Executor", level=logging.DEBUG)
        
        self.stdOut = None
        self.stdErr = None
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
    
    
    def _debugDetails(self, indent = 4):
        r = ""
        ind = ' ' * indent
        for k, v in self.__dict__.items():
            # not interested in methods
            if isinstance(v, types.MethodType):
                continue
            r = ind.join([r, "'%s': '%s'\n" % (k, v)])
        return r

    
    def getLogs(self):
        self.stdOut.seek(0) # move pointer back to beginning before read()
        self.stdErr.seek(0)
        delim = 78 * '-'
        stdOutMsg = ("%s\nstdout:\n%s\n%s\nstderr:\n%s\n%s" %
                    (delim,
                     self.stdOut.read(),
                     delim,
                     self.stdErr.read(),
                     delim))
        return stdOutMsg


    def _handleBlockingProcess(self):
        """
        Blocking scenario, e.g. FDT client party.
        
        """
        # add into container of running processes, should process hang
        # for ever on wait()
        if self.caller != None:
            self.caller.addExecutor(self)
                
        m = "Waiting for '%s' (PID: %s) to finish ..." % (self.command,
                                                          self.proc.pid)
        self.logger.info(m)        
        # waits here
        # however, when the client process gets killed upon a
        # CleanupProcessesAction this call would fail with
        # OSError: [Errno 10] No child processes
        # check #8 description
        try:
            self.returncode = self.proc.wait()
        except OSError, ex:
            self.logger.error("Waiting for process to complete failed "
                              "(crashed/killed?), reason: %s" % ex)
            self.returncode = str(ex)
        
        # process finished here, remove it from executors container
        # do not remove itself from executors, subsequent
        # CleanupProcessesAction may
        # be left out of context and this executor instance gets orphaned
        #if self.caller != None:
        #    self.caller.removeExecutor(self)
        
        logs = self.getLogs()
        
        # considered returncodes for a synchronous call
        if self.returncode == 0:
            m = ("Command '%s' finished, no error raised, return code: "
                 "'%s'\nlogs:\n%s" % (self.command, self.returncode, logs))
            # comment out now: e.g. in case of FDT Java client error, the
            # process output logs are logged 3 times. the only issue is
            # when fdtcp initiator crashes, there is nowhere to send logs then
            # the same comment applies below ... 
            #self.logger.info(m) # log locally at fdtd side
            return m
        else:
            m = ("Command '%s' failed, return code: "
                 "'%s'\nlogs:\n%s" % (self.command, self.returncode, logs))
            #self.logger.error(m) # log locally at fdtd side
            raise ExecutorException(m)

    
    def _handleLogOutputWaiting(self):
        startTime = datetime.datetime.now()
        while True:
            time.sleep(0.5)
            self.logger.debug("Waiting for log output: '%s' from "
                              "non-blocking process (PID: %s) ..." %
                              (self.logOutputToWaitFor, self.proc.pid))
            logs = self.getLogs()
            
            if logs.rfind(self.logOutputToWaitFor) > -1:
                self.logger.debug("Expected output '%s' captured, continue "
                                  "(PID: %s)." % (self.logOutputToWaitFor,
                                                  self.proc.pid))
                break
            self.returncode = self.proc.poll()
            if self.returncode > -sys.maxint:
                self.logger.debug("Checked process (PID: %s) likely "
                                  "failed." % self.proc.pid)
                break
            # there is a danger of infinite looping - the process will be
            # running and the captured output log will be different
            # this depends on FDT Java particular output not being changed ...
            # hence this additional check:
            checkTime = datetime.datetime.now()
            if (checkTime - startTime).seconds > self.logOutputWaitTime:
                if self.returncode == None:
                    self.logger.error("Output log waiting time (%s seconds) "
                                      "is over and the process seems to run "
                                      "fine ..." % self.logOutputWaitTime)
                    break
                else:
                    #should not really happen - see .poll() above ...
                    pass
        return logs
    
            
    def _handleNonBlockingProcess(self):
        """
        Non-blocking scenario, e.g. FDT server party.
        caller is the creator of this Executor class instance.
        caller, if provided, has to have addExecutor() and removeExecutor()
        methods by which this instance registers / de-registers.        
        
        """
        # register newly created process with the caller, even if it fails
        # so that subsequent CleanupProcesses action knows about it
        if self.caller != None:
            self.caller.addExecutor(self)    
        
        # if provided, check self.logOutputToWaitFor for non-blocking
        # process output indicating that the process has really reliably
        # started
        if self.logOutputToWaitFor:
            logs = self._handleLogOutputWaiting()
        else:
            time.sleep(1)
            logs = self.getLogs()
            
        # in case of failure - does return the same returncode as above
        # this next .poll() calls has to be here, above condition might have
        # escaped through log check (i.e. before .poll() call)
        self.returncode = self.proc.poll()
        
        if self.returncode == None:
            m = ("Command '%s' is running (PID: %s) ...\nlogs:\n%s" %
                 (self.command, self.proc.pid, logs))
            return m
        else:
            m = ("Command '%s' failed, returncode: '%s'\nlogs:\n%s" %
                 (self.command, self.returncode, logs))
            #self.logger.error(m) # log locally
            raise ExecutorException(m)

    
    def _prepareLogFiles(self):
        # create tmp files for stdOut, stdErr of the process (w+ - read/write)
        self.stdOut = tempfile.TemporaryFile("w+")
        self.stdErr = tempfile.TemporaryFile("w+")

        if self.catchLogs:
            return {"stdout": self.stdOut, "stderr" : self.stdErr}
        else:
            m = "<catching disabled on request>\n"
            self.stdOut.write(m)
            self.stdErr.write(m)
            return {}


    def execute(self):
        logsConf = self._prepareLogFiles()
        
        self.logger.debug("Executing:\n%s" %  self._debugDetails())
        
        # sanity check - if process of the current action id is not
        # already present in the caller's executor container
        if self.caller != None:
            if self.caller.checkExecutorPresence(self):
                m = ("There already is executor associated with request "
                     "id '%s' in the caller (FDTD) container! Duplicate "
                     "request? Something wasn't not cleared up properly?" %
                     self.id)
                raise ExecutorException(m)
        
        # subprocess.Popen() requires arguments in a sequence, if run
        # with shell=True argument then could take the whole string      
        try:
            self.proc = subprocess.Popen(self.command.split(), **logsConf)
        # python 2.4.3 subprocess doesn't have subprocess.CalledProcessError            
        except OSError, ex:
            # logs should be available
            logs = self.getLogs()
            m = ("Command '%s' failed, reason: "
                 "%s\nlogs:\n%s" % (self.command, ex, logs))
            raise ExecutorException(m)
        
        if self.blocking:
            return self._handleBlockingProcess()
        else:
            return self._handleNonBlockingProcess()
