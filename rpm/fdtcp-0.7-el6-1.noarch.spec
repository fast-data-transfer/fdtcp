# rpmrebuild autogenerated specfile

%define defaultbuildroot /
AutoProv: no
%undefine __find_provides
AutoReq: no
%undefine __find_requires
# Do not try autogenerate prereq/conflicts/obsoletes and check files
%undefine __check_files
%undefine __find_prereq
%undefine __find_conflicts
%undefine __find_obsoletes
# Be sure buildpolicy set to do nothing
%define __spec_install_post %{nil}
# Something that need for rpm-4.1
%define _missing_doc_files_terminate_build 0

%define _binary_filedigest_algorithm 1
%define _binary_payload w9.gzdio

BuildArch:     noarch
Name:          fdtcp
Version:       0.7
Release:       1
License:       Caltech
Group:         System Environment/Daemons
Summary:       client/server tools for running persistent fdt services
URL:           https://twiki.cern.ch/twiki/bin/view/Main/ANSE

Provides:      config(fdtcp) = 0.7
Provides:      fdtcp = 0.7
Requires:      /bin/sh
Requires:      /usr/bin/env
Requires:      fdt
Requires:      openjdk
Requires:      jpackage-utils
Requires:      psutil
Requires:      pyro
Requires:      python(abi) = 2.6
Requires:      python-apmon

#suggest
#enhance
%description
client/server tools for running persistent fdt services.
%files
%defattr(0644, root, root, 0755)
%dir %attr(0755, fdt, fdt) "/etc/fdtcp"
%attr(0644, fdt, fdt) "/etc/fdtcp/fdtcp.conf"
%attr(0644, fdt, fdt) "/etc/fdtcp/fdtd-system-conf.sh"
%attr(0644, fdt, fdt) "/etc/fdtcp/fdtd.conf"
%attr(0755, root, root) "/etc/rc.d/init.d/fdtd"
%attr(0777, root, root) "/usr/bin/fdtcp"
%attr(0777, root, root) "/usr/bin/fdtd"
%attr(0777, root, root) "/usr/bin/fdtd-log_analyzer"
%attr(0755, root, root) "/usr/bin/wrapper_fdt.sh"
%attr(0755, root, root) "/usr/bin/wrapper_kill.sh"
%dir "/usr/lib/python2.6/site-packages/fdtcplib"
"/usr/lib/python2.6/site-packages/fdtcplib/__init__.py"
%dir "/usr/lib/python2.6/site-packages/fdtcplib/common"
"/usr/lib/python2.6/site-packages/fdtcplib/common/TransferFile.py"
"/usr/lib/python2.6/site-packages/fdtcplib/common/__init__.py"
"/usr/lib/python2.6/site-packages/fdtcplib/common/actions.py"
"/usr/lib/python2.6/site-packages/fdtcplib/common/errors.py"
%attr(0755, root, root) "/usr/lib/python2.6/site-packages/fdtcplib/fdtcp.py"
%attr(0755, root, root) "/usr/lib/python2.6/site-packages/fdtcplib/fdtd-log_analyzer.py"
%attr(0755, root, root) "/usr/lib/python2.6/site-packages/fdtcplib/fdtd.py"
%dir "/usr/lib/python2.6/site-packages/fdtcplib/utils"
"/usr/lib/python2.6/site-packages/fdtcplib/utils/Config.py"
"/usr/lib/python2.6/site-packages/fdtcplib/utils/Executor.py"
"/usr/lib/python2.6/site-packages/fdtcplib/utils/Logger.py"
"/usr/lib/python2.6/site-packages/fdtcplib/utils/__init__.py"
"/usr/lib/python2.6/site-packages/fdtcplib/utils/utils.py"
%dir %attr(0755, fdt, fdt) "/var/log/fdtd"
%dir %attr(0755, fdt, fdt) "/var/run/fdtd"

%pre -p /bin/sh
getent group fdt >/dev/null || groupadd -r fdt
getent passwd fdt >/dev/null || \
       useradd -r -g fdt -c "FDT service user" \
       -s /sbin/nologin -d /etc/fdtcp fdt
exit 0

%post -p /bin/sh
/sbin/chkconfig --add fdtd

%preun -p /bin/sh
if [ "$1" = "0" ]; then
    /sbin/service fdtd stop > /dev/null 2>&1
    /sbin/chkconfig --del fdtd
fi

%postun -p /bin/sh
if [ "$1" -ge "1" ] ; then
    /sbin/service fdtd condrestart >/dev/null 2>&1 || :
fi

%changelog
* Fri Oct 17 2014 Vlad Lapadatescu <vlad@cern.ch> 0.7
- removed grid authentication
- fixed reporting issue for PhEDEx when copyjob consisted of multiple src-dest pairs

* Thu Nov 11 2013 Vlad Lapadatescu <vlad@cern.ch> 0.6
- removed any hadoop dependencies from the configuration files
- parametrised and updated some hardcoded flags that were passed to the FDT client and server
- modified fdtd.py to listen on all interfaces instead of just one
- Removed the "-f" flag passed on to the FDT server restricting which clients can connect to the machine

* Mon Oct 14 2013 Vlad Lapadatescu <vlad@caltech.edu> 0.5
- removed hadoop related stuff
- updated fdtd.conf and parametrised some hardcoded attributes
- updated MonaLISA reporting interval to 5 seconds
- updated README

* Thu Jul 05 2012 Zdenek Maxa <at hep.caltech.edu> 0.4.11-2
- re-building with Python 2.6

* Fri May 20 2011 Zdenek Maxa <at hep.caltech.edu> 0.4.11-1
- log analyzer implemented, transfer performance distribution plot
- minor changes in logging

* Thu Apr 28 2011 Zdenek Maxa <at hep.caltech.edu> 0.4.9-1
- issues encountered, observed during #5 transfer test addressed - usually,
  additional checks and logging on issues #41, #32, #38

* Thu Apr 21 2011 Zdenek Maxa <at hep.caltech.edu> 0.4.4-1
- minor fixes

* Wed Apr 20 2011 Zdenek Maxa <at hep.caltech.edu> 0.4.3-1
- some further fixes and enhancements related to the previous iteration
  of phedex Nebraska -> Caltech debug transfers, details and description
  of recently closed tickets:
  https://trac.hep.caltech.edu/trac/fdtcp/report/10

* Tue Apr 12 2011 Zdenek Maxa <at hep.caltech.edu> 0.4.0-1
- some further fixes and enhancements related to the previous iteration
  of phedex Nebraska -> Caltech debug transfers, details and description
  of recently closed tickets:
  https://trac.hep.caltech.edu/trac/fdtcp/report/10

* Thu Apr 07 2011 Zdenek Maxa <at hep.caltech.edu> 0.3.16
- number of enhancements and fixes - details and description of recently
  closed tickets:
  https://trac.hep.caltech.edu/trac/fdtcp/report/10

* Mon Oct 04 2010 Michael Thomas <thomas@hep.caltech.edu> 0.3.3-2
- Hard code path to system python area to work around phedex
  using a private python installation.
- Remove sample FDT.pm to avoid unwanted perl dependencies

* Mon Oct 04 2010 Michael Thomas <thomas@hep.caltech.edu> 0.3.3-1
- Hard code path to system python area to work around phedex
  using a private python installation.

* Mon Sep 27 2010 Michael Thomas <thomas@hep.caltech.edu> 0.3.2-3
- Include sample FDT.pm phedex module

* Thu Sep 09 2010 Michael Thomas <thomas@hep.caltech.edu> 0.3.2-2
- Bump release for initial koji build

* Sat Sep 04 2010 Michael Thomas <thomas@hep.caltech.edu> 0.3.2-1
- Update to latest upstream release with better authservice logging

* Thu Sep 02 2010 Michael Thomas <thomas@hep.caltech.edu> 0.3.0-1
- Update to latest upstream release

* Wed Sep 01 2010 Michael Thomas <thomas@hep.caltech.edu> 0.2.6-4
- Add missing dependency on python-apmon

* Wed Sep 01 2010 Michael Thomas <thomas@hep.caltech.edu> 0.2.6-3
- Replace references to xrootd with fdtd in init script

* Wed Sep 01 2010 Michael Thomas <thomas@hep.caltech.edu> 0.2.6-2
- Update init script to match the new fdtd command line arguments

* Wed Sep 01 2010 Michael Thomas <thomas@hep.caltech.edu> 0.2.6-1
- New upstream release daemonizable fdtcp service.

* Wed Aug 25 2010 Michael Thomas <thomas@hep.caltech.edu> 0.2.2-3
- Fix broken symlinks and make binary python scripts executable

* Tue Aug 24 2010 Michael Thomas <thomas@hep.caltech.edu> 0.2.2-2
- New upstream release with improvements for packaging
- Create a fdt system user

* Mon Aug 23 2010 Michael Thomas <thomas@hep.caltech.edu> 0.2.1-1
- Initial version

