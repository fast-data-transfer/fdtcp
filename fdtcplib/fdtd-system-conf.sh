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
JAVA_LIBS=/usr/share/java

JAVA_HOME=/usr/java/latest

# AuthService, AuthClient Java applications - part of the project
AUTHSERVICEJAR=$JAVA_LIBS/fdtcp/authservice.jar
AUTHCLIENTJAR=$JAVA_LIBS/fdtcp/authclient.jar

# jar file of the FDT Java application
FDTJAR=$JAVA_LIBS/fdt.jar
# Hadoop adapter for FDT Java server side
FDTHDFSJAR=$JAVA_LIBS/fdt-hdfs.jar
# Hadoop dependencies of the FDT HDFS adapter (Hadoop 0.20)
FDTHDFSLIBS=/usr/lib/hadoop/hadoop-core.jar:/usr/lib/hadoop/lib/commons-logging-1.0.4.jar


# Grid Authentication Java libraries
GSILIBS=$JAVA_LIBS/cog-jglobus/cog-jglobus.jar:$JAVA_LIBS/cog-jglobus/puretls.jar:$JAVA_LIBS/cog-jglobus/junit.jar:$JAVA_LIBS/cog-jglobus/cryptix-asn1.jar:$JAVA_LIBS/cog-jglobus/cog-url.jar:$JAVA_LIBS/cog-jglobus/log4j-1.2.13.jar:$JAVA_LIBS/cog-jglobus/commons-logging-1.1.jar:$JAVA_LIBS/cog-jglobus/cog-jobmanager.jar:$JAVA_LIBS/cog-jglobus/jce-jdk13-131.jar:$JAVA_LIBS/cog-jglobus/cryptix32.jar:$JAVA_LIBS/cog-jglobus/cryptix.jar:$JAVA_LIBS/cog-jglobus/jgss.jar


# GSI authentication settings - should be adjusted locally, if necessary,
# and appropriate ownership set
X509_CERT_DIR=/etc/grid-security/certificates
X509_SERVICE_KEY=/etc/grid-security/fdt/fdtkey.pem
X509_SERVICE_CERT=/etc/grid-security/fdt/fdtcert.pem
GRIDMAPFILE=/etc/grid-security/grid-mapfile
