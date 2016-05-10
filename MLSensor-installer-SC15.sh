#!/bin/bash
#
#

myreplace(){
        a=`echo $1 | sed 's/\//\\\\\//g'`
        b=`echo $2 | sed 's/\//\\\\\//g'`
        cat | sed "s/$a/$b/g"
}

replace_in_file(){
        cat $1 | myreplace "$2" "$3" > $1.new
        rm -f $1
        mv $1.new $1
}

echo "This will MLSensor and start it afterwards."
echo

# Username...
BATCH_MODE=true

CRONTAB=${CRONTAB:-Y}
STARTMLSENSOR=${STARTMLSENSOR:-Y}
USEU=${USEU:-U}
PREFIX1=$PWD
PREFIX=${PREFIX:-$PREFIX1}

WGET="wget "
echo
echo "Preparing install dir..."
mkdir -p $PREFIX
cd $PREFIX
PREFIX=$PWD

if [ -x $PREFIX/MLSensor/bin/MLSensor ]; then
    echo "Seems that MLSensor is installed. Will try to stop it first (if running)"
    $PREFIX/MLSensor/bin/MLSensor stop
fi

rm -rf MLSensor

# Install MLSensor
MLSENSOR_KIT="MLSensor.tgz"
echo "Downloading MLSensor..."
if [ "$USEU" == "E" -o "$USEU" == "e" ] ; then
	$WGET http://monalisa.cern.ch/MLSensor/$MLSENSOR_KIT -O $MLSENSOR_KIT ||
	$WGET http://monalisa.caltech.edu/MLSensor/$MLSENSOR_KIT -O $MLSENSOR_KIT
else
	$WGET http://monalisa.caltech.edu/MLSensor/$MLSENSOR_KIT -O $MLSENSOR_KIT ||
	$WGET http://monalisa.cern.ch/MLSensor/$MLSENSOR_KIT -O $MLSENSOR_KIT 
fi

if [ ! -s "$MLSENSOR_KIT" ] ; then
	echo "Failed to download MLSensor."
	echo "Please check connectivity to monalisa.cern.ch and monalisa.caltech.edu"
	exit 3
fi

gzip -dc $MLSENSOR_KIT | tar xf -

rm -f $MLSENSOR_KIT

replace_in_file MLSensor/etc/mlsensor.properties "localhost:56884" "131.215.207.16:8884"

if [ "$STARTMLSENSOR" == "y" -o "$STARTMLSENSOR" == "Y" ] ; then
	echo
	echo "Starting MLSensor with $PREFIX/MLSensor/bin/MLSensor start ..."
	$PREFIX/MLSensor/bin/MLSensor start
fi

echo
echo "Done."
