"""
py.test unittest testsuite for common.TransferFile

__author__ = Zdenek Maxa

"""


import os
import sys
import logging

import py.test
from mock import Mock

from fdtcplib.common.TransferFile import TransferFile


def testTransferFileInstanceAttributesAccess():
    """test existence of necessary attributes"""
    transferFile = TransferFile("file1", "file2")
    print transferFile.fileSrc
    print transferFile.fileDest
    print transferFile.result
        

def testTransferFileStr():
    transferFile = TransferFile("file1", "file2")
    assert "file1 / file2" == str(transferFile)
