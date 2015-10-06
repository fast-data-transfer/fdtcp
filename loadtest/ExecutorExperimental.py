"""
__author__ = Zdenek Maxa

Component for running external commands.

Possibility to associate ID with the command (job) and username (running
processes under arbitrary usernames).

Handling standard output, standard error streams.

This is a load-test helper script used for development / testing of the
Executor

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

from utils.Logger import Logger
from utils.utils import getHostName



class ExecutorException(Exception):
    pass


class Executor(object):
    """Executing external process."""
        
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
                 logger=None):
        # id of the associated action / request
        self.id = id
        # actual command to execute in the process
        self.command = command
        # boolean flag - blocking / non-blocking process, in case of
        # blocking, wait until the process finished
        self.blocking = blocking
        # caller is the creator of this Executor class instance, if caller is
        # provided, it has to have addExecutor() and removeExecutor()
        # methods by which this instance registers / de-registers itself
        # with the upper layer (its invoker)
        self.caller = caller
        # whether or not to capture stdout, stderr logs
        self.catchLogs = catchLogs
        # in case of non-blocking process (and if it's a service running on
        # a port) keep track of this port
        self.port = port
        # if the process is run via sudo, keep track of the sudo-owner of this
        # process (i.e. of this Executor) - needed when killing this process
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
        # process failed
        self.logOutputWaitTime = logOutputWaitTime # [seconds]
        
        self.logger = logger or Logger(name="Executor",
                                       level=logging.DEBUG)
        
        self.stdOut = None
        self.stdErr = None
        # process instance as created by subprocess.Popen
        self.proc = None
        # returncode from the underlying self.proc instance
        self.returncode = None
                
        
    def __str__(self):
        return "process PID: %s '%s'" % (self.proc.pid, self.command)
    
    
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
        m = ("Waiting for '%s' (pid: %s) to finish ..." %
             (self.command, self.proc.pid))
        self.logger.info(m)
        
        # add into container of running processes, should process hang
        # for ever on wait()
        if self.caller != None:
            self.caller.addExecutor(self)
        
        self.returncode = self.proc.wait() # waits here
        
        # process finished here, remove it from the container of
        # running processes
        if self.caller != None:
            self.caller.removeExecutor(self)
        
        logs = self.getLogs()
        
        # considered returncodes for a synchronous call
        if self.returncode == 0:
            self.logger.info("Command '%s' finished, no error raised, "
                             "return code: '%s'\nlogs:\n%s" %
                             (self.command, self.returncode, logs))
            return logs
        else:
            m = ("Command '%s' failed, return code: "
                 "'%s'\nlogs:\n%s" % (self.command, self.returncode, logs))
            #self.logger.error(m)
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
            # this depends on FDT Java particular output not being
            # changed ... hence this additional check:
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
            self.logger.info("Command '%s' is running (pid: %s) ..." %
                            (self.command, self.proc.pid))
        else:
            m = ("Command '%s' failed, returncode: '%s'\nlogs:\n%s" %
                 (self.command, self.returncode, logs))
            #self.logger.error(m) # log locally
            raise ExecutorException(m)

        # register newly created process with the caller
        if self.caller != None:
            self.caller.addExecutor(self)
            
        return logs

    
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
        self.logger.info("Executing command: '%s' ..." % self.command)
        
        # subprocess.Popen() requires arguments in a sequence, if run
        # with shell=True argument then could take the whole string      
        try:
            self.proc = subprocess.Popen(self.command.split(), **logsConf)
        # python 2.4.3 subprocess doesn't have subprocess.CalledProcessError            
        except OSError, ex:
            # logs should be available
            logs = self.getLogs()
            m = ("Command '%s' failed, reason: %s\nlogs:\n%s" %
                 (self.command, ex, logs))
            raise ExecutorException(m)
        
        if self.blocking:
            return self._handleBlockingProcess()
        else:
            return self._handleNonBlockingProcess()
