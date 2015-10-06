# sitelib for noarch packages, sitearch for others (remove the unneeded one)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Name:           fdtcp
Version:        0.4.4
Release:        1%{?dist}
Summary:        client/server tools for running persistent fdt services

Group:          System Environment/Daemons
License:        Caltech
URL:            https://twiki.cern.ch/twiki/bin/view/Main/PhEDExFDTIntegration
# Source0 was generated with the commands (versions and tag adjusted ...):
# hg -v --debug clone /var/mercurial/fdtcp fdtcp-00-04-03
# hg archive -r fdtcp-00-04-03 -t tgz ../fdtcp-0.4.3.tgz 
Source0:        fdtcp-%{version}.tgz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

# We'll need java and related libraries when we are ready to
# build the authenticators from source.
#BuildRequires:  jdk ant cog-jglobus
Requires:       fdt jdk jpackage-utils cog-jglobus pyro python-apmon psutil
BuildArch:      noarch

%description
%{summary}.

%prep
%setup -q -n fdtcp-%{version}


%build
# Uncomment these when we're ready to build from source
#cd authenticator
#ant jars


%install
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT%{_bindir}
mkdir -p $RPM_BUILD_ROOT%{_sysconfdir}/%{name}/
install -p -m 0644 fdtcplib/fdtd-system-conf.sh $RPM_BUILD_ROOT%{_sysconfdir}/%{name}/
install -p -m 0644 fdtcplib/fdtd.conf $RPM_BUILD_ROOT%{_sysconfdir}/%{name}/
install -p -m 0644 fdtcplib/fdtcp.conf $RPM_BUILD_ROOT%{_sysconfdir}/%{name}/

# Install the authenticator jars
mkdir -p $RPM_BUILD_ROOT%{_javadir}/%{name}
install -p -m 0644 authenticator/*.jar $RPM_BUILD_ROOT%{_javadir}/%{name}/

# Install the python libraries
mkdir -p $RPM_BUILD_ROOT%{python_sitelib}/fdtcplib/common/
mkdir -p $RPM_BUILD_ROOT%{python_sitelib}/fdtcplib/utils/
install -p -m 0644 fdtcplib/*.py $RPM_BUILD_ROOT%{python_sitelib}/fdtcplib/
install -p -m 0644 fdtcplib/common/*.py $RPM_BUILD_ROOT%{python_sitelib}/fdtcplib/common/
install -p -m 0644 fdtcplib/utils/*.py $RPM_BUILD_ROOT%{python_sitelib}/fdtcplib/utils/
chmod 0755 $RPM_BUILD_ROOT%{python_sitelib}/fdtcplib/fdtd.py
chmod 0755 $RPM_BUILD_ROOT%{python_sitelib}/fdtcplib/fdtcp.py
chmod 0755 $RPM_BUILD_ROOT%{python_sitelib}/fdtcplib/fdtd-log_analyzer.py

# Link to the fdt client and server clt
mkdir -p $RPM_BUILD_ROOT%{_bindir}
ln -s %{python_sitelib}/fdtcplib/fdtd.py $RPM_BUILD_ROOT%{_bindir}/fdtd
ln -s %{python_sitelib}/fdtcplib/fdtcp.py $RPM_BUILD_ROOT%{_bindir}/fdtcp
ln -s %{python_sitelib}/fdtcplib/fdtd-log_analyzer.py $RPM_BUILD_ROOT%{_bindir}/fdtd-log_analyzer

# Install the three sudo wrapper scripts
install -p -m 0755 wrapper_fdt.sh $RPM_BUILD_ROOT%{_bindir}/
install -p -m 0755 wrapper_kill.sh $RPM_BUILD_ROOT%{_bindir}/
install -p -m 0755 authenticator/wrapper_auth.sh $RPM_BUILD_ROOT%{_bindir}/

# Install the fdtd init script
mkdir -p $RPM_BUILD_ROOT%{_initrddir}/
install -p -m 0755 fdtd.sh $RPM_BUILD_ROOT%{_initrddir}/fdtd

# Create the log directories
mkdir -p $RPM_BUILD_ROOT%{_var}/log/fdtd
mkdir -p $RPM_BUILD_ROOT%{_var}/run/fdtd

%check
# Nothing to test!

%clean
rm -rf $RPM_BUILD_ROOT


%pre
getent group fdt >/dev/null || groupadd -r fdt
getent passwd fdt >/dev/null || \
       useradd -r -g fdt -c "FDT service user" \
       -s /sbin/nologin -d /etc/fdtcp fdt
exit 0

%post
/sbin/chkconfig --add fdtd

%preun
if [ "$1" = "0" ]; then
    /sbin/service fdtd stop > /dev/null 2>&1
    /sbin/chkconfig --del fdtd
fi

%postun
if [ "$1" -ge "1" ] ; then
    /sbin/service fdtd condrestart >/dev/null 2>&1 || :
fi

%files
%defattr(-,root,root,-)
%doc README
%attr(-,fdt,fdt) %config(noreplace) %{_sysconfdir}/fdtcp
%{_bindir}/wrapper_*.sh
%{_bindir}/fdtd
%{_bindir}/fdtcp
%{_bindir}/fdtd-log_analyzer
%{python_sitelib}/fdtcplib
%{_javadir}/%{name}
%{_initrddir}/fdtd
%attr(-,fdt,fdt) %{_var}/log/fdtd
%attr(-,fdt,fdt) %{_var}/run/fdtd

%changelog
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

* Thu Apr 7 2011 Zdenek Maxa <at hep.caltech.edu> 0.3.16
- number of enhancements and fixes - details and description of recently
  closed tickets:
  https://trac.hep.caltech.edu/trac/fdtcp/report/10

* Mon Oct 4 2010 Michael Thomas <thomas@hep.caltech.edu> 0.3.3-2
- Hard code path to system python area to work around phedex
  using a private python installation.
- Remove sample FDT.pm to avoid unwanted perl dependencies

* Mon Oct 4 2010 Michael Thomas <thomas@hep.caltech.edu> 0.3.3-1
- Hard code path to system python area to work around phedex
  using a private python installation.

* Mon Sep 27 2010 Michael Thomas <thomas@hep.caltech.edu> 0.3.2-3
- Include sample FDT.pm phedex module

* Thu Sep 9 2010 Michael Thomas <thomas@hep.caltech.edu> 0.3.2-2
- Bump release for initial koji build

* Sat Sep 4 2010 Michael Thomas <thomas@hep.caltech.edu> 0.3.2-1
- Update to latest upstream release with better authservice logging

* Thu Sep 2 2010 Michael Thomas <thomas@hep.caltech.edu> 0.3.0-1
- Update to latest upstream release

* Wed Sep 1 2010 Michael Thomas <thomas@hep.caltech.edu> 0.2.6-4
- Add missing dependency on python-apmon

* Wed Sep 1 2010 Michael Thomas <thomas@hep.caltech.edu> 0.2.6-3
- Replace references to xrootd with fdtd in init script

* Wed Sep 1 2010 Michael Thomas <thomas@hep.caltech.edu> 0.2.6-2
- Update init script to match the new fdtd command line arguments

* Wed Sep 1 2010 Michael Thomas <thomas@hep.caltech.edu> 0.2.6-1
- New upstream release daemonizable fdtcp service.

* Wed Aug 25 2010 Michael Thomas <thomas@hep.caltech.edu> 0.2.2-3
- Fix broken symlinks and make binary python scripts executable

* Tue Aug 24 2010 Michael Thomas <thomas@hep.caltech.edu> 0.2.2-2
- New upstream release with improvements for packaging
- Create a fdt system user

* Mon Aug 23 2010 Michael Thomas <thomas@hep.caltech.edu> 0.2.1-1
- Initial version
