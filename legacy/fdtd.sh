#!/bin/bash
#
# fdtd Script to control fdt data transfer service
#    (e.g. /usr/bin/fdtd (fdtd.py))
#
# Author:     Zdenek Maxa <zdenek.maxa@hep.caltech.edu>
#
# chkconfig: - 90 10
# description:  Starts and stops the data transfer service
# short-description:  Starts and stops the data transfer service

# functional code, eventually used Mike's much simplified version
#   (see the other fdtd.sh file)


# configuration of paths, deamon start settings, 
# full path to fdtd, pid file, and log files
# (values set in fdtd.conf file may be overriden by CLI options)
declare fdtdDaemonScript="/usr/bin/fdtd"
# this file will contain fdtd.py logging and also redirected both
# stdout, stderr
declare fdtdDaemonLog=/var/log/fdtd/fdtd.log
declare fdtdDaemonPidFile=/var/run/fdtd/fdtd.pid
# end of configuration which may potentially require modifications 

declare -i retVal=0
declare pidOfLastJob
declare pidOfRunningProcess


# source function library
if [ -f /etc/init.d/functions ] ; then
    . /etc/init.d/functions
elif [ -f /etc/rc.d/init.d/functions ] ; then
    . /etc/rc.d/init.d/functions
else
    echo "Could not find /etc/init.d/functions or /etc/rc.d/init.d/functions."
    exit 0
fi

# put some colors
declare resetCol="\033[0m"
declare textRed="\033[31m"
declare textGreen="\033[32m"

# avoid using root's TMPDIR
unset TMPDIR



checkIfRunning () {
    pidOfLastJob=`cat ${fdtdDaemonPidFile} 2> /dev/null`
    pidOfRunningProcess=`ps auxwww | grep -v -E '(grep|awk)' | awk '/${fdtdDaemonScript}/ {print $2}'`
    if [[ -z ${pidOfLastJob} && -z ${pidOfRunningProcess} ]] ; then
	# fdtd is stopped
	retVal=1
    elif [[ -n ${pidOfLastJob} && -z ${pidOfRunningProcess} ]] ; then
	# fdtd is dead but the PID file exists
	retVal=2
    elif [[ -z ${pidOfLastJob} && -n ${pidOfRunningProcess} ]] ; then
	# fdtd (${pidOfRunningProcess}) is running but it was not launched with this script
	retVal=3
    elif [[ $pidOfLastJob == $pidOfRunningProcess ]] ; then
	# fdtd (${pidOfLastJob}) is running ...
	retVal=0
    else
	# fdtd (${pidOfRunningProcess}) is running but it was not launched with this
	# script: PID in file -> ${pidOfLastJob}; PID in memory -> ${pidOfRunningProcess}
	retVal=4
    fi
}

start() {
    checkIfRunning
    if (( retVal == 3 || retVal == 0 || retVal == 4 )) ; then
	echo -e "${textRed}The fdtd service is running.${resetCol}\nCheck the following list for processes:${textGreen}"
	ps auxwww | grep -v grep | grep -E '.*${fdtdDaemonScript}.*'
	echo -e "${resetCol}End of the list.\nIf the list is empty, remove ${fdtdDaemonPidFile} and restart the service."
    else
	echo -n "Starting the fdtd service daemon: "
	${fdtdDaemonScript} --logFile ${fdtdDaemonLog} --pidFile ${fdtdDaemonPidFile} --daemonize
	retVal=$?
	if [ $retVal -eq 0 ] ; then
	    echo_success
	    # PID of the daemon stores now the fdtd.py itself
	else
	    echo_failure
	fi
	echo
    fi
    return $retVal
}

stop() {
    checkIfRunning
    echo -n "Stopping the fdtd service daemon: "
    if (( retVal == 3 || retVal == 0 || retVal == 4 )) ; then
	# take the PID from the file (see in the function checkIfRunning)
	kill -15 ${pidOfLastJob}
	retVal=$?
    fi
    # fdtd.py itself shall take care of erasing ${fdtdDaemonPidFile}
    if [ $retVal -eq 0 ] ; then
	echo_success
    else
	echo_failure
    fi
    echo
    return $retVal
}

rhstatus() {
    checkIfRunning
    case $retVal in
	0)
	    echo "fdtd service daemon (${pidOfLastJob}) is running ..."
	    ;;
	1)
	    echo "fdtd service daemon is stopped."
	    ;;
	# perhaps points 2 - 4 can be removed ... trying to be too rigorous ...
	2)
	    echo "fdtd service daemon is dead but the PID file exists."
	    ;;
	3)
	    echo "fdtd service daemon (${pidOfRunningProcess}) is running but it was not launched with this script."
	    ;;
	4)
	    echo "fdtd service daemon (${pidOfRunningProcess}) is running but it was not launched with this script: PID in file -> ${pidOfLastJob}; PID in memory -> ${pidOfRunningProcess}."
	    ;;
    esac
    return $retVal
}

srvreset() {
    echo -e "Removing ${fdtdDaemonPidFile} ..."
    rm -fv ${fdtdDaemonPidFile}
}

restart() {
    stop
    start
}


# allow status as non-root.
if [ "$1" = status ]; then
    rhstatus
    exit $?
fi

case "$1" in
    start)
  	start
	;;
    stop)
  	stop
	;;
    restart)
  	restart
	;;
    reset)
	srvreset
	;;
    *)
	echo $"Usage: $0 {start|stop|restart}"
	exit 1
esac

exit $?
