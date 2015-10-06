"""
Module for application's configuration management.

The class is usually a base class for particular command line
interface.

The Config class handles configuration based on a configuration file
while defined command line options override values from the config file.

Instance of Config is a store of application's configuration values.

__author__ = Zdenek Maxa

"""


import os
import logging
import types
from ConfigParser import RawConfigParser
from optparse import OptionParser, TitledHelpFormatter



class ConfigurationException(Exception):
    """
    Erroneous config file or illegal CLI options detected.
    
    """
    pass


class Config(object):
    """
    Class holding various options and settings which are either predefined
    in the configuration file, overriding from command line options is
    considered.
       
    Subclass has to define self._options (dictionary)
    Subclass accesses self._parser to define command line interface
    
    """
    def __init__(self, args, configFileLocations=[], usage=None):
        """
        configFileLocations are full paths to the configuration files
        to use - first location which founds the file is taken, if
        the config file is not specified as a command line argument
        (config option).
        
        """    
        form = TitledHelpFormatter(width=78)
        self._parser = OptionParser(usage=usage,
                                    formatter=form,
                                    add_help_option=None)
        # implemented in the subclass - particular command line interface
        self.processCommandLineOptions(args)
        
        # self._options is now available - modify / add values according
        # to the values found in the config file
        self._processConfigFile(configFileLocations)
        
        
    def _parseConfigFile(self, fileName):
        if not os.path.exists(fileName):
            raise ConfigurationException("Config file %s does not exist." %
                                         fileName)
            
        # Raw - doesn't do any interpolation
        config = RawConfigParser()
        # by default it seems that value names are converted to lower case,
        # this way they should be case-sensitive
        config.optionxform = str
        config.read(fileName) # does not fail even on non existing file
        try:
            # assume only one section 'general'
            for (name, value) in config.items("general"):
                # setting only values which do not already exist, if a value
                # already exists - it means it was specified on the command
                # line and such value takes precedence over configuration file
                # beware - attribute may exist from command line parser
                # and be None - then set proper value here
                if self.get(name) == None: 
                    self._options[name] = value
                    
                # to some strings types processing ...
                if isinstance(self.get(name), types.StringType):
                    #convert 'True', 'False' strings to bool values
                    # True, False
                    if value.lower() == 'true':
                        self._options[name] = True
                    if value.lower() == 'false':
                        self._options[name] = False
                                        
                # if the configuration value is string and has been defined
                # (in config file or CLI) with surrounding " or ', remove that
                # have to check type because among self._mandatoryStr may be
                # boolean types ...
                r = self.get(name)
                if isinstance(r, types.StringType):
                    if r[0] in ("'", '"'):
                        r = r[1:]
                    if r[-1] in ("'", '"'):
                        r = r[:-1]
                    self._options[name] = r
        except Exception, ex:            
            m = "Error while parsing %s, reason %s" % (fileName, ex)
            raise ConfigurationException(m)
        
        # safe location of the file from which the configuration was loaded
        # apart from this newly defined config value, there will also be
        # 'config' which remains None, unless specific config file
        # specified on CLI
        self._options["currentConfigFile"] = fileName 
        
        
    def _processConfigFile(self, locations):
        """
        Name of the configuration file may be specified
        as a command line option, otherwise default file is taken.
        At this moment, there either is some self._options[config]
        containing the path to the configuration file or default locations
        will be used
        
        """
        if self._options.get("config", None):
            self._parseConfigFile(self._options["config"])
        else:
            for name in locations:
                # first existing file is taken
                if os.path.exists(name):
                    break
            else:
                msg = ("No configuration provided / found, tried: %s" %
                       locations)
                raise ConfigurationException(msg)
            self._parseConfigFile(name)
            

    def processCommandLineOptions(self, args):
        m = ("processCommandLineOptions() not implemented, Config must be "
             "subclassed.")
        raise NotImplementedError, m


    def get(self, what):        
        r = self._options.get(what, None)
        # if not defined - return None
        return r
        
        
    def sanitize(self):
        """
        Checks that all mandatory configuration values are present and
        have sensible values.
        
        """
        # convert integer values to integers
        for opt in self._mandatoryInt:
            try:
                v = self.get(opt)
                i = int(v)
                self._options[opt] = i
            except (ValueError, TypeError):
                m = ("Illegal option '%s', expecting integer, got '%s'" %
                     (opt, v))
                raise ConfigurationException(m)
        
        # checks only presence
        for opt in self._mandatoryInt + self._mandatoryStr:
            if self.get(opt) == None: # have to test specifically None
                raise ConfigurationException("Mandatory option '%s' not "
                                             "set." % opt)
            
        # debug value is in fact string, need to convert it into proper
        # logging level value (and test its validity)
        name = self.get("debug")
        try:
            level = getattr(logging, name)
            self._options["debug"] = level
        except AttributeError:
            raise ConfigurationException("Wrong value of debug output "
                                         "level ('%s')." % name)
