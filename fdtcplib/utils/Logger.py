"""
Wrapper class for logging module (standard Python module).

__author__ = Zdenek Maxa

"""

import sys
import traceback
import linecache
import logging
import pprint
import types



class Logger(logging.getLoggerClass()):
    """
    Customised Logger. Logging either to console or into a file.
    
    """

    def __init__(self, name="Logger", logFile=None, level=logging.DEBUG):
        """
        Input check: if file doesn't exist, it's created. Wrong file name or
        insufficient rights result into IOError which is propagated.
        Check that level is int and one of the values from logging constants
        added, since passing e.g. str value "DEBUG" results into empty log
        file and disappearing log messages.
        
        """
        self.myName = name
        self.myLogFile = logFile
        
        if type(level) is not types.IntType:
            m = ("Wrong level '%s' option. Must be integer constant from "
                 "logging module." % level)
            raise Exception(m)

        # handler for logging into a file, optional
        self.logFile = logFile
        self._logFileHandler = None
        self._logFileHandlerOpen = False

        # initialise logger, necessary!
        logging.Logger.__init__(self, name)

        # should be set for further created handlers
        self.setLevel(level)

        # %(name)-12s gives name as given here: name = "Logger"
        #fs = "%(asctime)s %(name)-8s %(levelname)-9s %(message)s"
        fs = "%(levelname)-9s %(asctime)s %(name)-8s %(message)s"
        self._myFormatter = logging.Formatter(fs)

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
        
        self.pp = pprint.PrettyPrinter(indent = 4)
        
        m =("Logger instance initialised (level: %s, log file: %s)\n%s" %
            (self._myLevel, self.logFile, 78 * '=')) 
        self._myLog(logging.DEBUG, m)
        
        
    def _myLog(self, level, msg, traceBack=False):
        """
        Single entry-point method to emit the log message.
        
        """
        if traceBack:
            # get last exception traceback
            # add traceback below the normal 'msg' message
            trace = self.getTracebackSimple()
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
            m = ("Attempt to log into already closed '%s', temporarily "
                 "reopening for log message: ..." % self.logFile) 
            self.log(logging.CRITICAL, m)
            self.log(level, msg)
            self.log(logging.CRITICAL, "Closing '%s' ..." % self.logFile)
            tmpHandler.flush()
            tmpHandler.close()
            return
        self.log(level, msg)


    def close(self):
        # can't be put into __del__() - gives error (file already closed)
        self._myLog(logging.WARNING, "Logger closing.\n\n\n")
        if self._logFileHandler:
            self._logFileHandler.flush()
            self._logFileHandler.close()
            self._logFileHandlerOpen = False

            
    def isOpen(self):
        return self._logFileHandlerOpen
        

    def getTracebackSimple(self):
        """
        Returns formatted traceback of the most recent exception.
        
        """
        # sys.exc_info() most recent exception
        trace = traceback.format_exception(*sys.exc_info())
        noExcepResponse = ['None\n'] 
        # this is returned when there is no exception
        if trace == noExcepResponse:
            return None
        tbSimple = "".join(trace)  # may want to add '\n'
        return tbSimple


    def getTracebackComplex(self, localsLevels=5):
        """
        Returns formatted traceback of the most recent exception.
        Could write into a file-like object (argument would be
        output = sys.stdout), now returns result in formatted string.
        
        """
        tbComplex = "".join([78 * '-', '\n'])
        tbComplex = "".join([tbComplex, "Problem: %s\n" % sys.exc_info()[1]])
        
        trace = sys.exc_info()[2]
        stackString = []
        while trace is not None:
            frame = trace.tb_frame
            lineno = trace.tb_lineno
            code = frame.f_code
            filename = code.co_filename
            function = code.co_name
            if filename.endswith(".py"):
                line = linecache.getline(filename, lineno)
            else:
                line = None
            stackString.append((filename, lineno, function, line, frame))
            trace = trace.tb_next

        tbComplex = "".join([tbComplex, "Traceback:\n"])
        localsLevel = max(len(stackString) - localsLevels, 0)
        for i in range(len(stackString)):
            (filename, lineno, name, line, frame) = stackString[i]
            outputLine = (" File '%s', line %d, in %s (level %i):\n" %
                         (filename, lineno, name, i))
            tbComplex = "".join([tbComplex, outputLine])
            if line:
                tbComplex = "".join([tbComplex, "  %s\n" % line])
            if i >= localsLevel:
                # want to see complete stack if exception came from a template
                pass
        
        tbComplex = "".join([tbComplex, 78 * '-', '\n'])

        del stackString[:]
        frame = None
        trace = None
        return tbComplex


    def _setWrapperMethods(self):
        """
        This method makes sure that all possible logging methods:
            warning, warn, fatal, error, debug, critical, info will be
            called via _myLog(self, level, msg)
        
        """
        pass
        """
        for met, level in (('warning',  logging.WARNING),
                           ('warn',     logging.WARNING),
                           ('fatal',    logging.FATAL),
                           ('error',    logging.ERROR),
                           ('debug',    loggign.DEBUG),
                           ('critical', logging.CRITICAL),
                           ('info',     logging.INFO)):
        by using functools and partial evaluation it would be possible
        to define all these methods dynamically, but functools are
        only available in Python 2.5 and higher, for how has to be made
        manually (below)
        """

    
    def warning(self, msg):
        self._myLog(logging.WARNING, msg)

    
    def warn(self, msg):
        self._myLog(logging.WARNING, msg)

        
    def fatal(self, msg, traceBack=False):
        self._myLog(logging.FATAL, msg)

        
    def error(self, msg, traceBack=False):
        self._myLog(logging.ERROR, msg, traceBack=traceBack)

        
    def debug(self, msg, traceBack=False):
        self._myLog(logging.DEBUG, msg, traceBack=traceBack)

        
    def critical(self, msg, traceBack=False):
        self._myLog(logging.CRITICAL, msg, traceBack=traceBack)
        
        
    def info(self, msg):
        self._myLog(logging.INFO, msg)

    
    def pprintFormat(self, obj):
        r = self.pp.pformat(obj)
        return r
        
    
    def __del__(self):
        pass
    
    
    def __str__(self):
        r = "%s name:%s level:%s logFile:%s" % (self.__class__.__name__,
                                                self.myName, self._myLevel,
                                                self.myLogFile)
        return r
