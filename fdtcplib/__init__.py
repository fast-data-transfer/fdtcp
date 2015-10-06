import os

# if the scripts are run from non-write directories, PYRO complains that
# PYRO_STORAGE env. variable points to "no write access" directory
# according to http://www.xs4all.nl/~irmen/pyro3/manual/3-install.html
# PYRO uses this directory for data like log files.
# This variable can be set in the PYRO configuration file (which is not used
# here) and it has to be done even before first PYRO import. Changing
# Pyro.config.PYRO_STORAGE in your program leads to unexpected results,
# because the initilization has already been done using the old value.


def checkWriteableDir(path):
    if os.access(path, os.W_OK):
        return
    else:
        m = ("PYRO_STORAGE env. variable set or attempt to set to "
             "'%s', but the location is not writeable." % path)
        raise RuntimeError(m)
        

# don't change the setting if the variable has been deliberately set before
path = os.environ.get("PYRO_STORAGE", None)
if not path:
    home = os.getenv("HOME")
    path = os.path.join(home, ".pyro_storage")
    if not os.path.exists(path):
        os.mkdir(path)
    checkWriteableDir(path)
    os.environ["PYRO_STORAGE"] = path
else:
    checkWriteableDir(path)
