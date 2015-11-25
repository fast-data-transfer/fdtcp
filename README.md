FDT - PhEDEx integration project (fdtcp)

This experimental integration project is aimed at linking CMS (CERN Compact
Muon Solenoid [1]) data transfers system PhEDEx [2] and Caltech's high-perf
data transfer application FDT (Fast Data Transfer) [3]. The ultimate goal is
to bring dynamic network circuits provided by the DYNES (Dynamic Network
Services) [4], which is an Internet2 project funded by NSF (National Science
Foundation), to CMS data transfers. The DYNES plug-in for FDT application
exists and the purpose of fdtcp is to integrate FDT with high-level and
claimed to be network-agnostic system PhEDEx.
The fdtcplib projects provides CLI utilities and daemon fdtd application
which are Python wrappers for FDT application. Grid authentication via Grid
Map File, third-party transfers and various other features necessary for
integration with PhEDEx are implemented here.
The test transfers were realized between Caltech and Nebraska Tier2 CMS
centres utilizing HDFS (Hadoop Distributed File System).

More on:
    https://twiki.cern.ch/twiki/bin/view/Main/PhEDExFDTIntegration
    doc/fdtcp_chep2010_proceedings.pdf

[1] http://cms.web.cern.ch/
[2] https://cmsweb.cern.ch/phedex/
[3] http://monalisa.cern.ch/FDT/
[4] http://iopscience.iop.org/1742-6596/396/4/042065/pdf/1742-6596_396_4_042065.pdf
