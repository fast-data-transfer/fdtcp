#!/bin/sh
#
# /etc/init.d/fdtd - Start/stop the fdtd services
#
# The following two lines allow this script to be managed by the
# chkconfig program.
#
# chkconfig: - 80 30
# description: fdtd is a file transfer service

# Source function library.
. /etc/rc.d/init.d/functions

FDTDUSER=fdt

if [ -e /etc/sysconfig/fdtd ] ; then
    . /etc/sysconfig/fdtd
fi

start() {
    echo -n "Starting fdtd: "
    daemon --user $FDTDUSER --pidfile /var/run/fdtd/fdtd.pid /usr/bin/fdtd --logFile /var/log/fdtd/fdtd.log --pidFile /var/run/fdtd/fdtd.pid --daemonize $FDTD_OPTIONS
    RETVAL=$?
    echo
    [ $RETVAL -eq 0 ] && touch /var/lock/subsys/fdtd
}

# A function to stop a program.
stop() {
    echo -n "Shutting down fdtd (conditional, check log): "
    killproc -p /var/run/fdtd/fdtd.pid fdtd -1
    RETVAL=$?
    # TODO
    # check if returning a value from FDTD._signalHandler() will have any effect here (if shutdown is ignored)
    echo
    rm -f /var/lock/subsys/fdtd
    return $RETVAL
}

# A function to stop a program.
stopforce() {
    echo -n "Shutting down fdtd (forced): "
    killproc -p /var/run/fdtd/fdtd.pid fdtd -15
    RETVAL=$?
    echo
    rm -f /var/lock/subsys/fdtd
    return $RETVAL
}

restart() {
    stop
    start
    return $RETVAL
}

case $1 in 
'start')
    start
    ;;
'stop')
    stop
    ;;
'stopforce')
	stopforce
	;;
'status')
    status -p /var/run/fdtd/fdtd.pid fdtd
    ;;
'reload' | 'restart')
    restart
    ;;
'condrestart')
    [ -f /var/lock/subsys/fdtd ] && restart
    ;;

*)
    echo "usage: $0 {start|stop|stopforce|status|restart|condrestart}"
    ;;
esac

exit $?