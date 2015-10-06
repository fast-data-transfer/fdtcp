"""
py.test unittest testsuite for the Executor module.

__author__ = Zdenek Maxa

"""


import os
import sys
import signal
import tempfile
import time

import py.test
from mock import Mock

from fdtcplib.utils.Logger import Logger
from fdtcplib.utils.Executor import Executor, ExecutorException



class MockCaller(object):
    def __init__(self):
        self.processes = []
        

    def addExecutor(self, e): # will get called inside e.execute
        self.processes.append(e)
        

    def removeExecutor(self, e): # will get called inside e.execute
        self.processes.remove(e)
        

    def checkExecutorPresence(self, e):
        """
        Return True of executor.id is already registered in the
        _executors container, False otherwise.
        
        """
        if e in self.processes:
            return True
        else:
            return False

        

def getTempFile(content):
    f = tempfile.NamedTemporaryFile("w+") # read / write
    f.write(content)
    f.flush()
    f.seek(0)
    return f
    

def setup_module():
    pass


def teardown_module():
    pass


def testExecutorInstantiation():
    e = Executor("someid",
                 "mycommand",
                 blocking=True,
                 catchLogs=False,
                 port=10,
                 logOutputToWaitFor="my log output",
                 killTimeout=100) 
    assert e.id == "someid"
    assert e.caller == None
    assert e.command == "mycommand"
    assert e.blocking == True
    assert e.catchLogs == False
    assert e.port == 10
    assert e.logOutputToWaitFor == "my log output"
    assert e.logOutputWaitTime == 0
    assert e.userName == None
    assert e.killTimeout == 100
    assert isinstance(e.logger, Logger) == True

    assert e.stdOut == None
    assert e.stdErr == None
    # process instance as created by subprocess.Popen
    assert e.proc == None
    # returncode from the underlying self.proc instance
    assert e.returncode == None


def testExecutorBlocking():
    command = "ls -la1 /tmp"
    e = Executor("some_id",
                 command,
                 blocking=True,
                 caller=MockCaller())
    logs = e.execute()
    # test __str__ method
    print "running '%s'" % e
    print "logs:%s" % logs
    s = e.getLogs()
    
    e = Executor("some_id", command, blocking=True, caller=None)
    logs = e.execute()
    # test __str__ method
    print "running '%s'" % e
    print "logs:%s" % logs
    s = e.getLogs()
    

def testExecutorNonBlocking():
    # need long running job
    command = "dd if=/dev/zero of=/dev/null count=100000000 bs=102400"
    e = Executor("some_id", command, blocking=False, caller=MockCaller())
    try:
        e.execute()
        assert e.proc.poll() == None # means command is running
        assert len(e.caller.processes) == 1
    finally:
        os.kill(e.proc.pid, signal.SIGKILL)
    
    e = Executor("some_id", command, blocking=False, caller=None)
    try:
        e.execute()
        assert e.proc.poll() == None # means command is running
    finally:
        os.kill(e.proc.pid, signal.SIGKILL)
    

def testExecutorBlockingExceptionWrongCommand():
    command = "nonsensecommandnow"
    e = Executor("some_id", command, caller=MockCaller(), blocking=True)
    py.test.raises(ExecutorException, e.execute)
    e = Executor("some_id", command, caller=None, blocking=True)
    py.test.raises(ExecutorException, e.execute)


def testExecutorNonBlockingExceptionWrongCommand():
    command = "nonsensecommandnow"
    e = Executor("some_id", command, caller=MockCaller(), blocking=False)
    py.test.raises(ExecutorException, e.execute)
    e = Executor("some_id", command, caller=None, blocking=False)
    py.test.raises(ExecutorException, e.execute)

    
def testExecutorNonBlockingException():
    # should fail due to permission denied
    command = "cat /etc/shadow"
    e = Executor("some_id", command, caller=MockCaller(), blocking=False)
    try:
        py.test.raises(ExecutorException, e.execute)
        assert e.proc.poll() != None # means command failed
        # the command failed, but if the caller is specified, it is
        # stored in its container for subsequent cleanup
        assert len(e.caller.processes) == 1
    finally:
        # in fact should not be running
        try:
            os.kill(e.proc.pid, signal.SIGKILL)
        except OSError:
            pass


def testExecutorBlockingException():
    # should fail due to permission denied
    command = "cat /etc/shadow"
    e = Executor("some_id", command, caller=MockCaller(), blocking=True)
    py.test.raises(ExecutorException, e.execute)
    try:
        assert e.proc.wait() != 0 # means command failed
        # process has not been removed in
        # Executor._handleBlockingProcess()
        # remains in the executor container should there be required
        # context for some subsequent action
        assert len(e.caller.processes) == 1
    finally:
        # kill it (try it ...)
        try:
            os.kill(e.proc.pid, signal.SIGKILL)
        except OSError:
            pass
        
        
def testExecutorLogsCatching():
    outputLogs = """------------------------------------------------------------------------------
stdout:
output to stdout

------------------------------------------------------------------------------
stderr:
output to stderr

------------------------------------------------------------------------------"""
    script = """
echo "output to stdout" > /dev/stdout
echo "output to stderr" > /dev/stderr
"""
    f = getTempFile(script)
    command = "bash %s" % f.name
    e = Executor("some_id", command, caller=None, blocking=True)
    output = e.execute()
    logs = e.getLogs()
    
    
def testExecutorLogsNotCatching():
    outputLogs = """------------------------------------------------------------------------------
stdout:
<catching disabled on request>

------------------------------------------------------------------------------
stderr:
<catching disabled on request>

------------------------------------------------------------------------------"""
    script = """
echo "output to stdout" > /dev/stdout
echo "output to stderr" > /dev/stderr
"""
    f = getTempFile(script)
    command = "bash %s" % f.name
    e = Executor("some_id",
                 command,
                 caller=None,
                 catchLogs=False,
                 blocking=True)
    logs = e.execute()
    
    
def testExecutorNonBlockingWaitingForLogOutput():
    script = """
c=2
while [ $c -gt 0 ]
do
    echo "some undesired logging output"
    sleep 1
    let "c -= 1"
done
echo "expected logging output"
sleep 1
"""
    f = getTempFile(script)
    command = "bash %s" % f.name
    
    # wait for correct log output
    logOutputToWaitFor = "expected logging output"
    e = Executor("some_id",
                 command,
                 blocking=False,
                 logOutputToWaitFor=logOutputToWaitFor,
                 logOutputWaitTime=3)
    logs = e.execute()
    # the process shall be considered running - the expected log output
    # was captured
    assert e.returncode == None # the process 
    time.sleep(3)
    # internal Executor returncode hasn't been updated since the last call
    # chain: .execute()
    assert e.proc.poll() == 0 # by now shall finish with 0 (no errors)
    
    # wait for wrong log output
    logOutputToWaitFor = "EXPECTED LOGGING OUTPUT"
    # wait more than the time of running of script, it script will finish
    # though from here (for non-blocking long-running) process, it is as if
    # the process failed
    e = Executor("some_id",
                 command,
                 blocking=False,
                 logOutputToWaitFor=logOutputToWaitFor,
                 logOutputWaitTime=5)
    py.test.raises(ExecutorException, e.execute)
    
    # wait too short time, so it seems the process runs anyway and check that
    logOutputToWaitFor = "rubbish"
    e = Executor("some_id",
                 command,
                 blocking=False,
                 logOutputToWaitFor=logOutputToWaitFor,
                 logOutputWaitTime=1)
    logs = e.execute()
    time.sleep(0.5)
    # even after this time, the process shall still be running
    assert e.proc.poll() == None
    time.sleep(1)
    # by now it shall be finished
    assert e.proc.poll() == 0 
