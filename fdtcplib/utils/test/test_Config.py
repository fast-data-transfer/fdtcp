"""
py.test unittest testsuite for the Config module.

__author__ = Zdenek Maxa

"""


import os
import sys
import logging
import tempfile

import py.test
from mock import Mock

from fdtcplib.utils.Config import Config
from fdtcplib.utils.Config import ConfigurationException



def getTempFile(content):
    f = tempfile.NamedTemporaryFile("w+") # read / write
    f.write(content)
    f.flush()
    f.seek(0)
    return f

        
def testConfigCantInstanciate():
    inputOption = "rubbish"
    py.test.raises(NotImplementedError, Config, inputOption.split(), [])
    

class TestConfig(Config):
    # mandatory configuration options, have to be integers
    _mandatoryInt = ["port"]
    # mandatory configuration options, have to be strings
    _mandatoryStr = ["debug"]
    
    def __init__(self, args, configFileLocations = [], usage = None):
        Config.__init__(self,
                        args,
                        configFileLocations=configFileLocations,
                        usage=usage)


    def _defineCommandLineOptions(self):
        help = "debug output level, for possible values see the config file"
        self._parser.add_option("-d", "--debug", help = help)
        help = "print this help"
        self._parser.add_option("-h", "--help", help = help, action = 'help')
        help = "port of the service"
        self._parser.add_option("-p", "--port", help = help)
        help = "configuration file"
        self._parser.add_option("-c", "--config", help = help)
        help = "optional argument - output log file"
        self._parser.add_option("-l", "--logFile", help = help)
        

    def processCommandLineOptions(self, args):
        """This method gets called from base class"""
        self._defineCommandLineOptions()

        # opts - new processed options, items defined above appear as
        #   attributes
        # args - remainder of the input arrray
        opts, args = self._parser.parse_args(args = args)
        # want to have _options a dictionary, rather than instance
        # some Values class from within optparse.OptionParser
        #self._options = opts
        self._options = {}
        self._options = eval(str(opts))


def testConfigMandatoryOptions():
    c = """
[general]
port = 9000
debug = DEBUG
"""
    # all ok
    f = getTempFile(c)
    inputOption = "--config=%s" % f.name
    conf = TestConfig(inputOption.split())
    conf.sanitize()

    # empty configuration file, yet section defined
    c = """
[general]
"""
    f = getTempFile(c)

    # debug missing
    inputOption = "--port 1 --config=%s" % f.name
    conf = TestConfig(inputOption.split())
    py.test.raises(ConfigurationException, conf.sanitize)
    
    # port missing
    inputOption = "--debug DEBUG --config=%s" % f.name
    conf = TestConfig(inputOption.split())
    py.test.raises(ConfigurationException, conf.sanitize)

    # port missing value
    inputOption = "--port --debug DEBUG --config=%s" % f.name
    conf = TestConfig(inputOption.split())
    py.test.raises(ConfigurationException, conf.sanitize)
    
    # port not integer
    inputOption = "--port rubbish --debug DEBUG --config=%s" % f.name
    conf = TestConfig(inputOption.split())
    py.test.raises(ConfigurationException, conf.sanitize)

    # unsupported debug value
    inputOption = "--port 1 --debug DEBU --config=%s" % f.name
    conf = TestConfig(inputOption.split())
    py.test.raises(ConfigurationException, conf.sanitize)

    # all ok
    inputOption = "--port 1 --debug DEBUG --config=%s" % f.name
    conf = TestConfig(inputOption.split())
    conf.sanitize()
        

def testConfigFileDoesNotExistOrNotProvided():
    inputOption = "--config=/tmp/nonexistingconfig--not_existing"
    py.test.raises(ConfigurationException, TestConfig, inputOption.split())

    inputOption = "-c /tmp/nonexistingconfig--not_existing"
    py.test.raises(ConfigurationException, TestConfig, inputOption.split())
    

def testConfigEmptyFile():
    c = """
[general]
"""
    f = getTempFile(c)
    inputOption = "--config=%s" % f.name
    conf = TestConfig(inputOption.split())
    py.test.raises(ConfigurationException, conf.sanitize)
    
    # not having 'general' section - parsing exception
    c = """
"""
    f = getTempFile(c)
    inputOption = "--config=%s" % f.name
    py.test.raises(ConfigurationException, TestConfig, inputOption.split())


def testConfigValuesPreservingValuesOverriding():
    # assume one section 'general'
    c = """
[general]
# could do this if not sanitizing
port = 9000-1
debug = unsupported
"""
    f = getTempFile(c)
    inputOption = "--config=%s" % f.name
    conf = TestConfig(inputOption.split())
    
    assert conf.get("port") == "9000-1"
    assert conf.get("debug") == "unsupported"

    inputOption = "--port other --debug unsupported2 --config=%s" % f.name
    conf = TestConfig(inputOption.split())
    
    assert conf.get("port") == "other"
    assert conf.get("debug") == "unsupported2"    
        
    inputOption = "--config=%s -l /tmp/somefile" % f.name
    conf = TestConfig(inputOption.split())
    
    assert conf.get("port") == "9000-1"
    assert conf.get("debug") == "unsupported"
    assert conf.get("logFile") == "/tmp/somefile"
    

def testConfigConfigFileDefaultLocation():
    c = """
[general]
port = 9000
debug = DEBUG
"""
    f = getTempFile(c)
    inputOption = ""
    conf = TestConfig(inputOption.split(),
                      configFileLocations=[f.name],
                      usage="some usage")
    conf.sanitize()
