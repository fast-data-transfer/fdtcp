"""
Module for application's configuration management.

The class is usually a base class for particular command line
interface.

The Config class handles configuration based on a configuration file
while defined command line options override values from the config file.

Instance of Config is a store of application's configuration values.
"""
import os
import logging
from ConfigParser import RawConfigParser
from optparse import OptionParser, TitledHelpFormatter

from future import standard_library
standard_library.install_aliases()


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

    def __init__(self, args, configFileLocations=None, usage=None, mandInt=None, mandStr=None):
        """
        configFileLocations are full paths to the configuration files
        to use - first location which founds the file is taken, if
        the config file is not specified as a command line argument
        (config option).

        """
        if not configFileLocations:
            configFileLocations = []
        if not mandInt:
            mandInt = []
        if not mandStr:
            mandStr = []
        form = TitledHelpFormatter(width=78)
        self.parser = OptionParser(usage=usage,
                                   formatter=form,
                                   add_help_option=None)
        self.options = {}
        self.mandatoryInt = mandInt
        self.mandatoryStr = mandStr
        # implemented in the subclass - particular command line interface
        self.processCommandLineOptions(args)

        # self._options is now available - modify / add values according
        # to the values found in the config file
        self.processConfigFile(configFileLocations)

    def parseConfigFile(self, fileName):
        """ TODO doc """
        if not os.path.exists(fileName):
            raise ConfigurationException("Config file %s does not exist." %
                                         fileName)

        # Raw - doesn't do any interpolation
        config = RawConfigParser()
        # by default it seems that value names are converted to lower case,
        # this way they should be case-sensitive
        config.optionxform = str
        config.read(fileName)  # does not fail even on non existing file
        try:
            # assume only one section 'general'
            for (name, value) in config.items("general"):
                # setting only values which do not already exist, if a value
                # already exists - it means it was specified on the command
                # line and such value takes precedence over configuration file
                # beware - attribute may exist from command line parser
                # and be None - then set proper value here
                if self.get(name) is None:
                    self.options[name] = value

                # to some strings types processing ...
                if isinstance(self.get(name), bytes):
                    # convert 'True', 'False' strings to bool values
                    # True, False
                    if value.lower() == 'true':
                        self.options[name] = True
                    if value.lower() == 'false':
                        self.options[name] = False

                # if the configuration value is string and has been defined
                # (in config file or CLI) with surrounding " or ', remove that
                # have to check type because among self._mandatoryStr may be
                # boolean types ...
                rVal = self.get(name)
                if isinstance(rVal, bytes):
                    if rVal[0] in ("'", '"'):
                        rVal = rVal[1:]
                    if rVal[-1] in ("'", '"'):
                        rVal = rVal[:-1]
                    self.options[name] = rVal
        except Exception as ex:
            msg = "Error while parsing %s, reason %s" % (fileName, ex)
            raise ConfigurationException(msg)

        # safe location of the file from which the configuration was loaded
        # apart from this newly defined config value, there will also be
        # 'config' which remains None, unless specific config file
        # specified on CLI
        self.options["currentConfigFile"] = fileName

    def processConfigFile(self, locations):
        """
        Name of the configuration file may be specified
        as a command line option, otherwise default file is taken.
        At this moment, there either is some self._options[config]
        containing the path to the configuration file or default locations
        will be used

        """
        if self.options.get("config", None):
            self.parseConfigFile(self.options["config"])
        else:
            fname = ""
            for name in locations:
                # first existing file is taken
                if os.path.exists(name):
                    fname = name
                    break
            else:
                msg = ("No configuration provided / found, tried: %s" %
                       locations)
                raise ConfigurationException(msg)
            self.parseConfigFile(fname)

    def processCommandLineOptions(self, args):
        """ processCommandLineOptions() which is subclassed """
        del args
        msg = ("processCommandLineOptions() not implemented, Config must be "
               "subclassed.")
        raise NotImplementedError(msg)

    def get(self, what):
        """ Custom get from the options """
        val = self.options.get(what, None)
        # if not defined - return None
        return val

    def sanitize(self):
        """
        Checks that all mandatory configuration values are present and
        have sensible values.
        """
        # convert integer values to integers
        for opt in self.mandatoryInt:
            try:
                val = self.get(opt)
                i = int(val)
                self.options[opt] = i
            except (ValueError, TypeError):
                msg = ("Illegal option '%s', expecting integer, got '%s'" %
                       (opt, val))
                raise ConfigurationException(msg)

        # checks only presence
        for opt in self.mandatoryInt + self.mandatoryStr:
            if self.get(opt) is None:  # have to test specifically None
                raise ConfigurationException("Mandatory option '%s' not "
                                             "set." % opt)

        # debug value is in fact string, need to convert it into proper
        # logging level value (and test its validity)
        name = self.get("debug")
        try:
            level = getattr(logging, name)
            self.options["debug"] = level
        except AttributeError:
            raise ConfigurationException("Wrong value of debug output "
                                         "level ('%s')." % name)
