"""
test help script when developing *actions* classes logging of attributes.
to be run from the project root directory:
    python fdtcplib/common/test/logtest.py

""" 

from fdtcplib.common.actions import SendingClientAction
from fdtcplib.utils.Logger import Logger

transferFiles = ['/mnt/hadoop/user/uscms01/pnfs/unl.edu/data4/cms/store/phedex_monarctest/Nebraska/LoadTest07_Nebraska_65 / /mnt/hadoop/store/PhEDEx_LoadTest07/LoadTest07_Debug_US_Nebraska/US_Caltech/3962/LoadTest07_Nebraska_65_uprBpUmMbtrlF910_3962',
                 '/mnt/hadoop/user/uscms01/pnfs/unl.edu/data4/cms/store/phedex_monarctest/Nebraska/LoadTest07_Nebraska_AB / /mnt/hadoop/store/PhEDEx_LoadTest07/LoadTest07_Debug_US_Nebraska/US_Caltech/3962/LoadTest07_Nebraska_AB_VBggLIppuOd19CPC_3962',
                 '/mnt/hadoop/user/uscms01/pnfs/unl.edu/data4/cms/store/phedex_monarctest/Nebraska/LoadTest07_Nebraska_E3 / /mnt/hadoop/store/PhEDEx_LoadTest07/LoadTest07_Debug_US_Nebraska/US_Caltech/3962/LoadTest07_Nebraska_E3_nxS6pVoM1of60fNW_3962',
                 '/mnt/hadoop/user/uscms01/pnfs/unl.edu/data4/cms/store/phedex_monarctest/Nebraska/LoadTest07_Nebraska_0B / /mnt/hadoop/store/PhEDEx_LoadTest07/LoadTest07_Debug_US_Nebraska/US_Caltech/3962/LoadTest07_Nebraska_0B_QIG6aG9hpal8XTJD_3962',
                 '/mnt/hadoop/user/uscms01/pnfs/unl.edu/data4/cms/store/phedex_monarctest/Nebraska/LoadTest07_Nebraska_1B / /mnt/hadoop/store/PhEDEx_LoadTest07/LoadTest07_Debug_US_Nebraska/US_Caltech/3962/LoadTest07_Nebraska_1B_but3hjz0eT7bWHrr_3962',
                 '/mnt/hadoop/user/uscms01/pnfs/unl.edu/data4/cms/store/phedex_monarctest/Nebraska/LoadTest07_Nebraska_39 / /mnt/hadoop/store/PhEDEx_LoadTest07/LoadTest07_Debug_US_Nebraska/US_Caltech/3962/LoadTest07_Nebraska_39_mcBzPcNt1pJcaAkc_3962',
                 '/mnt/hadoop/user/uscms01/pnfs/unl.edu/data4/cms/store/phedex_monarctest/Nebraska/LoadTest07_Nebraska_81 / /mnt/hadoop/store/PhEDEx_LoadTest07/LoadTest07_Debug_US_Nebraska/US_Caltech/3962/LoadTest07_Nebraska_81_QueqvduaTBMjk3pu_3962',
                 '/mnt/hadoop/user/uscms01/pnfs/unl.edu/data4/cms/store/phedex_monarctest/Nebraska/LoadTest07_Nebraska_CB / /mnt/hadoop/store/PhEDEx_LoadTest07/LoadTest07_Debug_US_Nebraska/US_Caltech/3962/LoadTest07_Nebraska_CB_YbQNLdVZnUIEukVe_3962',
                 '/mnt/hadoop/user/uscms01/pnfs/unl.edu/data4/cms/store/phedex_monarctest/Nebraska/LoadTest07_Nebraska_1C / /mnt/hadoop/store/PhEDEx_LoadTest07/LoadTest07_Debug_US_Nebraska/US_Caltech/3962/LoadTest07_Nebraska_1C_3iyt9ymMVRpAVEWz_3962',
                 '/mnt/hadoop/user/uscms01/pnfs/unl.edu/data4/cms/store/phedex_monarctest/Nebraska/LoadTest07_Nebraska_62 / /mnt/hadoop/store/PhEDEx_LoadTest07/LoadTest07_Debug_US_Nebraska/US_Caltech/3962/LoadTest07_Nebraska_62_wboDVRwpaSU8jU0O_3962']

options = dict(port = 54321, hostDest = 'gridftp05.ultralight.org',
                      transferFiles = transferFiles,
                      gridUserSrc = 'cmsphedex')
s = SendingClientAction('fdtcp-cithep249.ultralight.org-phedex-2011-04-08--06h:19m:21s:822724mics-epjiu', options)

#logger = Logger(name = "fdtcp", logFile = "/tmp/logfile")
logger = Logger(name = "fdtcp")
uri = "some.machine.edu:333/PYRO"
logger.debug("Calling '%s' request: %s\n%s ..." %
             (uri, s.__class__.__name__, s))
logger.close()
logger.error("erroneous message")
