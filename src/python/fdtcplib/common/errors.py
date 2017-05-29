""" Custom FDTCP Exceptions """


class TimeoutException(Exception):
    """
    SIGALARM was sent to the process, interrupt current action.
    """
    pass


class FDTCopyException(Exception):
    """
    FDTCopy exception wrapping PYRO errors and various.

    """
    pass


class FDTCopyShutdownBySignal(FDTCopyException):
    """
    Exception passed around for signal handling at fdtcp side.
    """
    pass


class ServiceShutdownBySignal(Exception):
    """
    Is an exception-based signal to terminate the service daemon.
    """
    pass


class FDTDException(Exception):
    """
    FDTD daemon exception.
    """
    pass


class PortReservationException(FDTDException):
    """
    No port is available to be reserved, request has be to rejected.
    """
    pass


class PortInUseException(FDTDException):
    """
    No port is available to be reserved, request has be to rejected.
    """
    pass


class AuthServiceException(FDTDException):
    """
    Exception in the AuthService - Java GSI authentication service.
    """
    pass


class ExecutorException(Exception):
    """ Executor Exception. """
    pass


class CleanupProcessException(FDTDException):
    """
    Exception in Cleanup Process - Failed to clean process or called non existing method.
    """
    pass
