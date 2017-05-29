"""
if the scripts are run from non-write directories, PYRO complains that
PYRO_STORAGE env. variable points to "no write access" directory
according to http://www.xs4all.nl/~irmen/pyro3/manual/3-install.html
PYRO uses this directory for data like log files.
This variable can be set in the PYRO configuration file (which is not used
here) and it has to be done even before first PYRO import. Changing
Pyro.config.PYRO_STORAGE in your program leads to unexpected results,
because the initilization has already been done using the old value.
"""
import os


def checkWriteableDir(path):
    """ Check if write access to directory available """
    if os.access(path, os.W_OK):
        return
    else:
        msg = ("PYRO_STORAGE env. variable set or attempt to set to "
               "'%s', but the location is not writeable." % path)
        raise RuntimeError(msg)


# don't change the setting if the variable has been deliberately set before

PATH = os.environ.get("PYRO_STORAGE", None)
if not PATH:
    HOME = os.getenv("HOME")
    PATH = os.path.join(HOME, ".pyro_storage")
    if not os.path.exists(PATH):
        os.mkdir(PATH)
    checkWriteableDir(PATH)
    os.environ["PYRO_STORAGE"] = PATH
else:
    checkWriteableDir(PATH)
