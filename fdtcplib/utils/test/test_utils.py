"""
py.test unittest testsuite for the utils module - set of helper routines.

__author__ = Zdenek Maxa

"""


import os
import sys
import py.test

from fdtcplib.utils.utils import getHostName
from fdtcplib.utils.utils import getDateTime
from fdtcplib.utils.utils import getUserName
from fdtcplib.utils.utils import getRandomString
from fdtcplib.utils.utils import getOpenFilesList



def setup_module():
    pass


def teardown_module():
    pass


def testGetHostName():
    host = getHostName()
    assert isinstance(host, str)
    assert len(host) > 1
    
    
def testGetUserName():
    user = getUserName()
    assert os.environ["LOGNAME"] == user 
    assert isinstance(user, str)
    
    
def testGetDateTime():
    dateTime = getDateTime()
    assert isinstance(dateTime, str)
    assert len(dateTime) > 1
    
    
def testGetRandomString():
    calculated = []
    for i in range(0, 100):
        s = getRandomString('a', 'z', 10)
        assert s not in calculated
        calculated.append(s)
        

def testGetOpenFilesList():
    fileName = "/tmp/somefile"
    numFiles, filesList = getOpenFilesList()
    assert numFiles == 0
    assert filesList == '' # empty string result
    f = open(fileName, 'w')
    numFiles, filesList = getOpenFilesList(offset=0)
    assert numFiles == 1
    assert filesList.startswith(fileName)
    f.close()
    numFiles, filesList = getOpenFilesList()
    assert numFiles == 0
    os.remove(fileName)
