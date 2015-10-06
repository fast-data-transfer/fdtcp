#!/bin/sh

# phedex-fdt project - kill a process
# script runs via sudo, kills a process given the input PID

command="kill -9 $1"
echo "killing process PID $1 command: $command"
$command