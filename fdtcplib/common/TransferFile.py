"""
Single item of a transfer procedure - transferred file.
Has to be in a location easily accessible for both PYRO client and service.

__author__ = Zdenek Maxa

"""


class TransferFile(object):
    """
    Single item of a transfer procedure - transferred file.
    
    """
    def __init__(self, fileSrc, fileDest):
        self.fileSrc = fileSrc
        self.fileDest = fileDest
        # TODO implement per file result filling - must be coordinated
        # with FDT,  will be done later - currently FDT doesn't provide
        # per file results when fileList is used
        self.result = None  # result of the per file transfer
    

    def __str__(self):
        # the slash is used as separator for FDT Java client 
        # fileList file format
        return "%s / %s" % (self.fileSrc, self.fileDest)
    
    
    def __repr__(self):
        # the slash is used as separator for FDT Java client fileList
        # file format
        return "%s / %s" % (self.fileSrc, self.fileDest)
