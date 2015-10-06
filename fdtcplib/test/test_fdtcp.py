"""
py.test unittest testsuite for fdtcp

__author__ = Zdenek Maxa

"""


import os
import sys
import tempfile
import logging
import threading

import py.test
from mock import Mock

from fdtcplib.fdtcp import Transfer
from fdtcplib.fdtcp import Transfers
from fdtcplib.fdtcp import FDTCopy
from fdtcplib.fdtcp import ConfigFDTCopy
from fdtcplib.common.TransferFile import TransferFile
from fdtcplib.common.errors import FDTCopyException
from fdtcplib.utils.Logger import Logger
from fdtcplib.common.actions import TestAction, SendingClientAction
from fdtcplib.utils.Config import ConfigurationException



def testTransferInstanceAttributesAccess():
    """
    test existence of necessary attributes
    
    """
    transfer = Transfer(None, None, None)
    print transfer.id
    print transfer.hostSrc
    print transfer.hostDest
    print transfer.sender
    print transfer.receiver
    print transfer.files
    print transfer.log
    print transfer.result
    print transfer.toCleanup
    print transfer.logger
    print transfer.conf
    print transfer.portSrc
    print transfer.portDest


def testConfigRetrievingValues():
    inputOptions = "-f /tmp/batchfile"
    conf = ConfigFDTCopy(inputOptions.split())
    assert conf.get("report") == None
    
    inputOptions = "-r /tmp/report -f /tmp/batchfile"
    conf = ConfigFDTCopy(inputOptions.split())
    assert conf.get("nonsense") == None
    assert conf.get("report") == "/tmp/report"
    assert conf.get("copyjobfile") == "/tmp/batchfile"
    
    inputOptions = ("-r /tmp/report -f /tmp/batchfile "
                    "--config /tmp/configfile")
    # config file does not exist - will raise exception
    py.test.raises(ConfigurationException,
                   ConfigFDTCopy,
                   inputOptions.split())
    
    inputOptions = "fdt://host1:123:/file1 fdt://host2:124/file2"
    conf = ConfigFDTCopy(inputOptions.split())
    assert conf.get("nonsense") == None
    assert conf.get("urlSrc") == "fdt://host1:123:/file1"
    assert conf.get("urlDest") == "fdt://host2:124/file2"


def testConfigCorrectInput():
    # examples of command line options - all correct
    # --copyjobfile and -f are the same options
    inputOptions = \
"""-r /tmp/report --copyjobfile=/tmp/batchfile -d DEBUG -t 3
-r /tmp/report -f /tmp/batchfile -d DEBUG -t 3
fdt://host1:123/tmp/file fdt://host2:124//tmp/file1 -d DEBUG -t 3
-r /tmp/report fdt://host1:123/tmp/file fdt://host2:123/tmp/file1 -d DEBUG -t 3"""
    for i in inputOptions.split('\n'):
        ops = i.strip()
        print "command line options: %s" % ops
        conf = ConfigFDTCopy(ops.split())
        conf.sanitize()
        
    
def testConfigIncorrectInput():
    inputOption = ("--copyjobfile=/tmp/batchfile "
                   "fdt://host1:123/tmp/file fdt://host2:123/tmp/file1")
    py.test.raises(ConfigurationException,
                   ConfigFDTCopy,
                   inputOption.split())
    
    inputOption = "-r /tmp/report -c /tmp/batchfile"
    # either src, dest must be specified or copyjobfile (-c is config file)
    py.test.raises(ConfigurationException, ConfigFDTCopy, inputOption.split())
    
    
def testTransferGeneral():
    logger = Logger("test logger",  level=logging.DEBUG)
    conf = ConfigFDTCopy("-r /tmp/report fdt://host1:123/tmp/file "
                         "fdt://host2:123/tmp/file1".split())
    apMon = None
    transfer = Transfer(conf, apMon, logger)
    
    
def testTransfersGeneral():
    logger = Logger("test logger",  level=logging.DEBUG)
    conf = ConfigFDTCopy("-r /tmp/report fdt://host1:123/tmp/file "
                         "fdt://host2:12355/tmp/file1".split())
    apMon = None
    transfers = Transfers(conf, apMon, logger)
    assert len(transfers.transfers) == 1
    assert len(transfers.transfers["host1:123-host2:12355"].files) == 1
    assert transfers.transfers["host1:123-host2:12355"].hostSrc == "host1" 
    assert transfers.transfers["host1:123-host2:12355"].portSrc == "123"
    assert transfers.transfers["host1:123-host2:12355"].files[0].fileSrc == \
            "/tmp/file"
    assert transfers.transfers["host1:123-host2:12355"].hostDest == "host2"
    assert transfers.transfers["host1:123-host2:12355"].portDest == "12355"
    assert transfers.transfers["host1:123-host2:12355"].files[0].fileDest == \
            "/tmp/file1"    
    assert transfers.transfers["host1:123-host2:12355"].result == 1
    

def testTransfersCopyJobFileNonExisting():
    logger = Logger("test logger",  level=logging.DEBUG)
    inputOption = "--copyjobfile=/tmp/nonexistingfile"
    conf = ConfigFDTCopy(inputOption.split())
    apMon = None
    py.test.raises(FDTCopyException, Transfers, conf, apMon, logger)


def testTransfersCopyJobFileWrongFormat():
    # blank lines (triple quotes not directly in front of the first line
    # should also cause exception being raised
    # non-numeric port numbers
    data = """
fdt://host1:123/tmp/file  host5:123/tmp/fileX1
fdt://host2:123234/tmp/file1
fdt://host2:14124/tmp/file3 host6:124/tmp/fileX
fdt://host2:14124c/tmp/file3 host6:124c/tmp/fileX
fdt://host2:14124/tmp/file3 fdt://host6:124c/tmp/fileX
fdt://host2:14124x/tmp/file3 fdt://host6:124/tmp/fileX
- -

"""
    logger = Logger("test logger",  level=logging.DEBUG)
    for line in data.split('\n'):
        copyJobFile = tempfile.NamedTemporaryFile("w+") # read / write
        print "copyjobfile contains: '%s'" % line
        copyJobFile.write(line)
        copyJobFile.flush()
        copyJobFile.seek(0)
    
        inputOption = "--copyjobfile=%s" % copyJobFile.name
        conf = ConfigFDTCopy(inputOption.split())
        apMon = None
        py.test.raises(FDTCopyException, Transfers, conf, apMon, logger)
        
    
def testTransfersCopyJobFile():
    # correct data
    data = \
"""fdt://host1:111/tmp/file  fdt://host5:222//tmp/fileX1
fdt://host2:555/tmp/fileGY fdt://host5:444/tmp/fileX2
fdt://host2:555/tmp/fileWA fdt://host5:444/tmp/fileX
fdt://host3:777/tmp/fileWQ  fdt://host7:888/tmp/fileTY
fdt://host4:999/tmp/file9Y  fdt://host8:1212/tmp/fileIO"""
    logger = Logger("test logger",  level=logging.DEBUG)
    copyJobFile = tempfile.NamedTemporaryFile("w+") # read / write
    copyJobFile.write(data)
    copyJobFile.flush()
    copyJobFile.seek(0)
    
    inputOption = "--copyjobfile=%s" % copyJobFile.name
    conf = ConfigFDTCopy(inputOption.split())
    apMon = None
    transfers = Transfers(conf, apMon, logger)
    
    assert len(transfers.transfers) == 4
    
    assert len(transfers.transfers["host1:111-host5:222"].files) == 1
    assert len(transfers.transfers["host2:555-host5:444"].files) == 2
    assert len(transfers.transfers["host3:777-host7:888"].files) == 1
    assert len(transfers.transfers["host4:999-host8:1212"].files) == 1

    # correct port numbers are tested as part of key to transfers.transfer
    assert transfers.transfers["host1:111-host5:222"].hostSrc == "host1"
    assert transfers.transfers["host1:111-host5:222"].hostDest == "host5"
    assert transfers.transfers["host1:111-host5:222"].files[0].fileSrc == \
        "/tmp/file"
    assert transfers.transfers["host1:111-host5:222"].files[0].fileDest == \
        "/tmp/fileX1"
    assert transfers.transfers["host2:555-host5:444"].hostSrc == "host2"
    assert transfers.transfers["host2:555-host5:444"].hostDest == "host5"
    assert transfers.transfers["host2:555-host5:444"].files[0].fileSrc == \
        "/tmp/fileGY"
    assert transfers.transfers["host2:555-host5:444"].files[0].fileDest == \
        "/tmp/fileX2"
    assert transfers.transfers["host2:555-host5:444"].files[1].fileSrc == \
        "/tmp/fileWA" 
    assert transfers.transfers["host2:555-host5:444"].files[1].fileDest == \
        "/tmp/fileX"
    assert transfers.transfers["host3:777-host7:888"].hostSrc == "host3"
    assert transfers.transfers["host3:777-host7:888"].hostDest == "host7"
    assert transfers.transfers["host3:777-host7:888"].files[0].fileSrc == \
        "/tmp/fileWQ"
    assert transfers.transfers["host3:777-host7:888"].files[0].fileDest == \
        "/tmp/fileTY"
    assert transfers.transfers["host4:999-host8:1212"].hostSrc == "host4"
    assert transfers.transfers["host4:999-host8:1212"].hostDest == "host8"
    assert transfers.transfers["host4:999-host8:1212"].files[0].fileSrc == \
        "/tmp/file9Y"
    assert transfers.transfers["host4:999-host8:1212"].files[0].fileDest == \
        "/tmp/fileIO"

    
def testTransfer():
    # correct data
    data = \
"""fdt://localhost1:111/tmp/file  fdt://localhost5:444/tmp/fileX1
fdt://localhost2:111/tmp/fileGY   fdt://localhost5:444/tmp/fileX2
fdt://localhost2:111/tmp/fileWA   fdt://localhost5:444/tmp/fileX
fdt://localhost3:111/tmp/fileWQ   fdt://localhost7:444/tmp/fileTY
fdt://localhost4:111/tmp/file9Y   fdt://localhost8:444/tmp/fileIO"""
    logger = Logger("test logger",  level=logging.DEBUG)
    copyJobFile = tempfile.NamedTemporaryFile("w+") # read / write
    copyJobFile.write(data)
    copyJobFile.flush()
    copyJobFile.seek(0)
    
    inputOption = "--copyjobfile=%s" % copyJobFile.name
    conf = ConfigFDTCopy(inputOption.split())
    
    # transfers actually fail with could not connect to remote PYRO
    # wrong hosts - no Transfer instances will be setUp()
    apMon = None
    transfers = Transfers(conf, apMon, logger)
    

def testInputCopyJobFileTranslationIntoFDTFileList():
    # correct data - input copyjobfile - all must be the same source host,
    # destination host pairs, otherwise such input copyjobfile will break
    # into a number of FDT fileList files on corresponding source hosts 
    inputData = \
"""fdt://localhost:111/tmp/file  fdt://localhost:222/tmp/fileX1
fdt://localhost:111/tmp/fileGY   fdt://localhost:222/tmp/fileX2
fdt://localhost:111/tmp/fileWA   fdt://localhost:222/tmp/fileX
fdt://localhost:111/tmp/fileWQ   fdt://localhost:222/tmp/fileTY
fdt://localhost:111/tmp/file9Y   fdt://localhost:222/tmp/fileIO"""

    # desired output fileList for FDT client
    outputData = \
"""/tmp/file / /tmp/fileX1
/tmp/fileGY / /tmp/fileX2
/tmp/fileWA / /tmp/fileX
/tmp/fileWQ / /tmp/fileTY
/tmp/file9Y / /tmp/fileIO"""
    
    logger = Logger("test logger",  level=logging.DEBUG)
    copyJobFile = tempfile.NamedTemporaryFile("w+") # read / write
    copyJobFile.write(inputData)
    copyJobFile.flush()
    copyJobFile.seek(0)
    
    inputOption = "--copyjobfile=%s" % copyJobFile.name
    conf = ConfigFDTCopy(inputOption.split())
    apMon = None
    transfers = Transfers(conf, apMon, logger)
    
    # since having the same source host, destination host pair, should have
    # only one transfer job
    t = transfers.transfers["localhost:111-localhost:222"]
    assert len(transfers.transfers) == 1
    assert len(t.files) == 5
    
    # do relevant stuff from fdtcp performTransfer method now
    testAction = TestAction(t.hostSrc, t.hostDest, timeout=5)
    t.id = testAction.id
    options = dict(port="some_port",
                   hostDest=t.hostDest,
                   transferFiles=t.files)
    sndClientAction = SendingClientAction(testAction.id, options)
    
    assert sndClientAction.options["port"] == "some_port"
    assert sndClientAction.options["hostDest"] == t.hostDest
    
    # fileList is constructed at the side of fdtd service (remote site)
    # simulate this process ...
    class MockFDTDConfig(Mock):
        # mock class only to satisfy sndClientAction._setUp() call - when
        # it checks for log file 
        def get(self, what):
            return "/tmp/logfile"
    # this method is called on fdtd service site
    sndClientAction._setUp(MockFDTDConfig())
    assert sndClientAction.options["fileList"] == \
        "/tmp/fileLists/fdt-fileList-%s" % sndClientAction.id

    # now check content of the fileList file - shall be as the output data
    data = open(sndClientAction.options["fileList"], 'r').readlines()
    for line1, line2 in zip(data, outputData.split('\n')):
        assert line1.strip() == line2
        
    # clean up after test, only if succeeded
    os.unlink(sndClientAction.options["fileList"])
