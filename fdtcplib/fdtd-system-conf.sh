# fdtcp project (configuration for fdtd service)

# this file contains system configuration settings that are sourced
# into bash wrapper scripts (wrapper_auth.sh, wrapper_fdt.sh) 
# (most) paths in this file shall be set automatically by the
# installation process

# settings for the FDT server only (not used by the FDT client)
# values related to the FDT-HDFS (Hadoop) adapter for FDT
# these values may be adjusted by the administrator

# allows to use /mnt/hadoop prefix in files URLs
# this var. was likely just necessary in Hadoop 0.19-2 but in 0.20 it is not
# necessary and in fact FDT fails with "Unable to create dir" when it's set
# Summer 2012 tests - both ends (Caltech, Nebraska Hadoop 0.20)
#export HADOOP_POSIX_PREFIX=/mnt/hadoop

# paths to required Java libraries
# should not need any modification if standard locations are used

# shortcut to the Java libraries directory
export JAVA_LIBS=/usr/share/java

export JAVA_HOME=/usr/java/latest

# AuthService, AuthClient Java applications - part of the project
export AUTHSERVICEJAR=$JAVA_LIBS/fdtcp/authservice.jar
export AUTHCLIENTJAR=$JAVA_LIBS/fdtcp/authclient.jar

# jar file of the FDT Java application
export FDTJAR=/home/dynes/fdt.jar
# Hadoop adapter for FDT Java server side
export FDTHDFSJAR=/home/dynes/OPT/fdtcp/javalibs/fdt-hdfs.jar
# Hadoop dependencies of the FDT HDFS adapter (Hadoop 0.20)
export FDTHDFSLIBS=/home/dynes/OPT/fdtcp/javalibs/hadoop-core.jar:/home/dynes/OPT/fdtcp/javalibs/commons-logging-1.0.4.jar

export TEMP_JAVA_LIBS=$JAVA_LIBS
export JAVA_LIBS=/home/dynes/OPT/fdtcp/authenticator/

# Grid Authentication Java libraries
# AuthService, AuthClient Java applications - part of the project
export AUTHSERVICEJAR=$JAVA_LIBS/authservice.jar
export AUTHCLIENTJAR=$JAVA_LIBS/authclient.jar
export GSILIBS=$JAVA_LIBS/cog-jglobus/cog-jglobus.jar:$JAVA_LIBS/cog-jglobus/puretls.jar:$JAVA_LIBS/cog-jglobus/junit.jar:$JAVA_LIBS/cog-jglobus/cryptix-asn1.jar:$JAVA_LIBS/cog-jglobus/cog-url.jar:$JAVA_LIBS/cog-jglobus/log4j-1.2.13.jar:$JAVA_LIBS/cog-jglobus/commons-logging-1.1.jar:$JAVA_LIBS/cog-jglobus/cog-jobmanager.jar:$JAVA_LIBS/cog-jglobus/jce-jdk13-131.jar:$JAVA_LIBS/cog-jglobus/cryptix32.jar:$JAVA_LIBS/cog-jglobus/cryptix.jar:$JAVA_LIBS/cog-jglobus/jgss.jar
export JAVA_LIBS=$TEMP_JAVA_LIBS

# GSI authentication settings - should be adjusted locally, if necessary,
# and appropriate ownership set
export X509_CERT_DIR=/etc/grid-security/certificates
export X509_SERVICE_KEY=/home/dynes/fdt-caltech.hep.caltech.edu-key.pem
export X509_SERVICE_CERT=/home/dynes/fdt-caltech.hep.caltech.edu.pem
export GRIDMAPFILE=/etc/grid-security/grid-mapfile
