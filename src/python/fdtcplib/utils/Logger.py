"""
Wrapper class for logging module (standard Python module).
"""
import sys
import logging
import pprint
from fdtcplib.utils.utils import getTracebackSimple


class Logger(logging.getLoggerClass()):
    """
    Customised Logger. Logging either to console or into a file.
    """

    def __init__(self, name="Logger", logFile=None, level=logging.INFO):
        """
        Input check: if file doesn't exist, it's created. Wrong file name or
        insufficient rights result into IOError which is propagated.
        Check that level is int and one of the values from logging constants
        added, since passing e.g. str value "DEBUG" results into empty log
        file and disappearing log messages.
        """
        self.myName = name
        self.myLogFile = logFile

        if not isinstance(level, int):
            msg = ("Wrong level '%s' option. Must be integer constant from "
                   "logging module." % level)
            raise Exception(msg)

        # handler for logging into a file, optional
        self.logFile = logFile
        self._logFileHandler = None
        self._logFileHandlerOpen = False

        # initialise logger, necessary!
        logging.Logger.__init__(self, name)

        # should be set for further created handlers
        self.setLevel(level)

        # %(name)-12s gives name as given here: name = "Logger"
        # fs = "%(asctime)s %(name)-8s %(levelname)-9s %(message)s"
        formatStr = "%(levelname)-9s %(asctime)s %(name)-8s %(message)s"
        self._myFormatter = logging.Formatter(formatStr)

        if not self.logFile:
            # logging to console, sys.stdout
            console = logging.StreamHandler(sys.stdout)
            console.setFormatter(self._myFormatter)
            self.addHandler(console)
        else:
            # log file has been specified, log into file rather than console
            self._logFileHandler = logging.FileHandler(self.logFile)
            self._logFileHandler.setLevel(level)
            self._logFileHandler.setFormatter(self._myFormatter)
            self.addHandler(self._logFileHandler)
            self._logFileHandlerOpen = True

        # should be first logging message
        self._myLevel = logging.getLevelName(self.getEffectiveLevel())

        self.nicePrint = pprint.PrettyPrinter(indent=4)

        msg = ("Logger instance initialised (level: %s, log file: %s)\n%s" %
               (self._myLevel, self.logFile, 78 * '='))
        self._myLog(logging.DEBUG, msg)

    def _myLog(self, level, msg, traceBack=False):
        """
        Single entry-point method to emit the log message.
        """
        if traceBack:
            # get last exception traceback
            # add traceback below the normal 'msg' message
            trace = getTracebackSimple()
            if not trace:
                trace = "<empty exception traceback>"
                msg = "%s\n\n%s\n\n" % (msg, trace)
            else:
                # trace will now include all previous exception message
                msg = trace

        if self.logFile and not self._logFileHandlerOpen:
            # logging into file enabled, yet the file seems to have been
            # closed log the message and close the file again
            tmpHandler = logging.FileHandler(self.logFile)
            tmpHandler.setLevel(self._myLevel)
            tmpHandler.setFormatter(self._myFormatter)
            self.addHandler(tmpHandler)
            msg = ("Attempt to log into already closed '%s', temporarily "
                   "reopening for log message: ..." % self.logFile)
            self.log(logging.CRITICAL, msg)
            self.log(level, msg)
            self.log(logging.CRITICAL, "Closing '%s' ...", self.logFile)
            tmpHandler.flush()
            tmpHandler.close()
            return
        self.log(level, msg)

    def close(self):
        """ Flush all logging handlers and close them."""
        # can't be put into __del__() - gives error (file already closed)
        self._myLog(logging.DEBUG, "Logger closing.\n\n\n")
        if self._logFileHandler:
            self._logFileHandler.flush()
            self._logFileHandler.close()
            self._logFileHandlerOpen = False

    def isOpen(self):
        """ check if logging handlers are still open """
        return self._logFileHandlerOpen

    def _setWrapperMethods(self):
        """
        This method makes sure that all possible logging methods:
            warning, warn, fatal, error, debug, critical, info will be
            called via _myLog(self, level, msg)
        """
        pass

    def warning(self, msg):
        """ Warning level """
        self._myLog(logging.WARNING, msg)

    def warn(self, msg):
        """ Warning level """
        self._myLog(logging.WARNING, msg)

    def fatal(self, msg):
        """ FATAL level """
        self._myLog(logging.FATAL, msg)

    def error(self, msg):
        """ Error level """
        self._myLog(logging.ERROR, msg)

    def debug(self, msg):
        """ Debug level """
        self._myLog(logging.DEBUG, msg)

    def critical(self, msg):
        """ Critical level """
        self._myLog(logging.CRITICAL, msg)

    def info(self, msg):
        """ Info level """
        self._myLog(logging.INFO, msg)

    def pprintFormat(self, obj):
        """ print formar of obj """
        retMsg = self.nicePrint.pformat(obj)
        return retMsg

    def __del__(self):
        pass

    def __str__(self):
        retMsg = "%s name:%s level:%s logFile:%s" % (self.__class__.__name__,
                                                     self.myName, self._myLevel,
                                                     self.myLogFile)
        return retMsg
