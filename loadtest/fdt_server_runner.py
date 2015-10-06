"""
This is a load-test helper script used for development / testing of the
Executor module. Simulates many concurrent requests for daemon / service
start up (FDT Java).

"""


import time
import threading

from utils.Logger import Logger
from ExecutorExperimental import Executor, ExecutorException



class PortReservationException(Exception):
    pass



class FDTService(object):
    # must be run from projects root directory    
    fdtReceivingServerCommand = "java -jar fdt/fdt.jar -bs 2M -p %(port)s -wCount 12 -S -noupdates"
    reserved = "54321,54400"

    
    def __init__(self, logger):
        self.logger = logger
        portMin, portMax = [int(i) for i in self.reserved.split(',')]
        self.portRange = range(portMin, portMax + 1)
        # will be secured by lock, mutual access to port
        # reservation / releasing
        self.portsTaken = set()
        self.portsTakenLock = threading.Lock()
        self.executors = {}
        self.executorsLock = threading.Lock()
        
    
    def _getFreePort(self):
        self.portsTakenLock.acquire(True)
        for port in self.portRange:
            if port not in self.portsTaken:
                break
        else:
            self.portsTakenLock.release()
            raise PortReservationException("No free port to reserve. %s "
                                           "ports taken." %
                                           len(self.portsTaken))
        self.portsTaken.add(port)
        self.portsTakenLock.release()
        self.logger.debug("Free port '%s' reserved." % port)
        return port
    
        
    def _releasePort(self, port):
        self.portsTakenLock.acquire(True)
        try:
            try:
                self.portsTaken.remove(port)
            except KeyError:
                self.logger.error("Trying to release a port which has not "
                                  "been taken (%s)." % port)
        finally:
            self.portsTakenLock.release()
            self.logger.debug("Reserved port '%s' released." % port)

        
    def service(self, id):
        """
        Called concurrently from many threads at a time - like
        fdtd .service() method.
        
        """
        try:
            port = self._getFreePort()
        except PortReservationException, ex:
            self.logger.error("Can't start service, reason: %s" % ex)
            return     
            
        logOutputToWaitFor = "FDTServer start listening on port: %s" % port
        command = self.fdtReceivingServerCommand % dict(port=port)
        
        executor = Executor(id,
                            command,
                            blocking=False,
                            caller=self, 
                            port=port,
                            logOutputToWaitFor=logOutputToWaitFor,
                            logOutputWaitTime=3,
                            logger=self.logger)
                                    
        try:
            self.logger.debug("-- service() %s" % (20 * '1'))
            logs = executor.execute()
            self.logger.debug("-- service() %s" % (20 * '2'))
        except ExecutorException, ex: 
            # logs should be present in the exception
            self.logger.debug("-- service() %s" % (20 * '4'))
            self._releasePort(port) 
            self.logger.error("Can't start service, reason: %s" % ex)
        except Exception, ex:
            self.logger.debug("-- service() %s" % (20 * '5'))
            self._releasePort(port)
            self.logger.error("Unknown exception occurred, reason: %s" %
                              ex, traceBack=True)
        else:
            self.logger.debug("-- service() %s" % (20 * '6'))
            self.logger.debug("%s runs on port '%s', logs:\n%s" %
                              (executor, port, logs))
        

    def addExecutor(self, executor):
        if executor.id in self.executors:
            m = ("There already is executor associated with request id "
                 "'%s' in container! Duplicate request? Something wasn't "
                 "not cleared up properly?" % executor.id)
            self.logger.error(m)
        else:
            self.executorsLock.acquire(True)
            self.executors[executor.id] = executor
            self.executorsLock.release()
            self.logger.debug("%s added to the executor container." %
                              executor)


    def removeExecutor(self, executor):
        self.executorsLock.acquire(True)
        try:
            del self.executors[executor.id]
        except KeyError:
            self.logger.error("Executor id '%s' not present in the "
                              "executors container." % executor.id)
        self.executorsLock.release()
        self.logger.debug("%s removed from the executor container." %
                          executor)
        
        
    def cleanUp(self, executorId):
        self.logger.debug("Going to kill executor process id '%s'" %
                           executorId)
        try:
            executor = self.executors[executorId]
        except KeyError:
            self.logger.error("Process/executor id '%s' doesn't exist in "
                              "the container." % executorId)
            return
        command = "kill -9 %s" % executor.proc.pid        
        id = "kill-%s" % executorId
        killExecutor = Executor(id,
                                command,
                                blocking=True,
                                logger=self.logger)
        
        try:
            logs = killExecutor.execute()
        except ExecutorException, ex:
            self.logger.error("Could not kill %s, reason: %s" %
                              (executor, ex))
        else:
            self.removeExecutor(executor)
            self._releasePort(executor.port)
            self.logger.debug("logs from the killed process:\n%s" %
                              executor.getLogs())

        
class ThreadCaller(threading.Thread):
    def __init__(self, id, actionName, whatToCall, logger):
        self.id = id
        self.actionName = actionName
        self.whatToCall = whatToCall
        self.logger = logger
        threading.Thread.__init__(self)
        self.logger.debug("thread initialized, action: '%s', id: '%s'" %
                          (self.actionName, self.id))
        
        
    def run(self):
        self.logger.debug("thread running, action: '%s', id: '%s'" %
                          (self.actionName, self.id))
        self.whatToCall(self.id)
        


def report(service, logger):
    """
    no waiting time - check if the Executor polling mechanism is realiable.
    
    """
    logger.debug("###################### reporting status ...")
    logger.debug("service: executors: '%s'" % len(service.executors))
    logger.debug("\texecutors processes: %s" % service.executors)
    logger.debug("\tports taken: %s" % service.portsTaken)

    
def main():
    logger = Logger(name="runner_test")
    service = FDTService(logger)
    report(service, logger)
    
    # number of FDT Java servers to create
    numServers = 3
    ids = ["request-%03d" % i for i in range(numServers)]
    
    threads = []
    for id in ids:
        runner = ThreadCaller(id, "FDT caller", service.service, logger)
        runner.start()
        threads.append(runner)
   
    # wait until all threads finish ... no matter how but must finish
    logger.info("Waiting for FDT caller threads to terminate ...")
    for t in threads:
        t.join()
        
    report(service, logger)     
        
    threads = []
    
    # commenting out this section - cleaning up and restarting the
    # script should show reliable failure reporting since the ports
    # occupied from the previous script run
    for id in ids:
        wiper = ThreadCaller(id, "FDT wiper", service.cleanUp, logger)
        wiper.start()
        threads.append(wiper)

    # wait until all threads finish ... no matter how but must finish
    logger.info("Waiting for FDT wiper threads to terminate ...")
    for t in threads:
        t.join()

    report(service, logger)


if __name__ == "__main__":
    main()  
