"""
py.test unittest testsuite for the Logger module.

__author__ = Zdenek Maxa

"""


import os
import sys
import logging
import re

import py.test

from fdtcplib.utils.Logger import Logger

    
TEST_LOG_FILE = "/tmp/testlogfile.log"


def testLogger():
    logger = Logger("test logger",  level=logging.DEBUG)
    logger.info("info message")
    logger.warn("warn message")
    logger.warning("warning message")
    logger.error("error message")
    logger.critical("critical message")
    logger.fatal("fatal message")
    logger.debug("debug message")
    logger.close()
    

def testLoggerFile():
    testFile = TEST_LOG_FILE
    if not os.path.exists(testFile):
        logger = Logger("test file logger",
                        logFile=testFile,
                        level=logging.INFO)
        testMessage = "testmessage"
        logger.info(testMessage)
        logger.close()
        line = open(testFile, 'r').readlines()
        os.remove(testFile)
        # not the last line which the logger closing plus 3 x \n , but
        # line before that
        last = line[-5].split()[-1]
        assert testMessage == last
    else:
        m = "Can't do logging into file test, file %s exists." % testFile
        py.test.fail(m)
    
        
def testLoggerWrongLogFile():
    testFile = "/dev/" + TEST_LOG_FILE
    print testFile
    py.test.raises(IOError, Logger, logFile=testFile, level=logging.DEBUG)


def testLoggerWrongLevelOption():
    testFile = TEST_LOG_FILE
    # mistake: DEBUG string instead of logging.DEBUG which is integer
    py.test.raises(Exception,
                   Logger,
                   "test logger",
                   logFile=testFile,
                   level="DEBUG")
        
        
def testTracebackSimple():
    logger = Logger("test logger",  level=logging.DEBUG)
    try:
        1/0
    except Exception:
        logger.getTracebackSimple()
        logger.error("exception", traceBack=True)
        logger.fatal("exception", traceBack=True)
    logger.close()
    

def testTracebackComplex():
    logger = Logger("test logger",  level=logging.DEBUG)
    try:
        1/0
    except Exception:
        logger.getTracebackComplex()
    logger.close()
    
    
def testLogIntoClosedLogFile():
    """
    Test writing into a closed logger. The logger should handle.
    
    """
    testFile = TEST_LOG_FILE
    for met, level in (('warning',  logging.WARNING),
                       ('warn',     logging.WARNING),
                       ('fatal',    logging.FATAL),
                       ('error',    logging.ERROR),
                       ('debug',    logging.DEBUG),
                       ('critical', logging.CRITICAL),
                       ('info',     logging.INFO)):
        if os.path.exists(testFile):
            m = "Can't do logging into file test, file %s exists." % testFile
            py.test.fail(m)
        logger = Logger("test file logger", logFile=testFile, level=level)
        testMessage = "testLogIntoClosedLogFile-%s" % met
        c = getattr(logger, met)
        logger.close()
        # log after closing the logger
        c(testMessage)
        # message to search for
        toSearchMsg = ("Attempt to log into already closed.*$\n.*%s" %
                       testMessage)
        pattObj = re.compile(toSearchMsg, re.MULTILINE)
        fd = open(testFile, 'r')
        match = pattObj.search(fd.read())
        if not match:
            m = ("Log file '%s' should contain log message '%s' - does "
                 "not." % (testFile, toSearchMsg))
            py.test.fail(m)
        os.remove(testFile)
        
        
def testLoggerTraceBackTrueOnNoException():
    logger = Logger("test file logger", level=logging.DEBUG)
    logger.debug("my msg", traceBack=True)


def teardown_function(function):
    if os.path.exists(TEST_LOG_FILE):
        os.unlink(TEST_LOG_FILE)
