"""
* generates a bash script containing all AuthClient commands for AuthService
* loadtest
* run
    cd loadtest
    python __file__

* it's necessary to source fdtd-system.conf before running the AuthClient

* running the AuthService counterpart:
  $FDTCP_HOME/authenticator/wrapper_auth.sh -DX509_CERT_DIR=$X509_CERT_DIR -DX509_SERVICE_KEY=$X509_SERVICE_KEY -DX509_SERVICE_CERT=$X509_SERVICE_CERT -DGRIDMAP=$GRIDMAPFILE -cp $GSILIBS:$FDTJAR:$AUTHSERVICEJAR authenticator.AuthService -p 9000 2>&1 | tee authservice.log
"""

# number of tests are iterated from 1
NUMTESTS = 100

# -u %(fileNameToStoreRemoteUserName)s
TEMPLATE = "$FDTCP_HOME/authenticator/wrapper_auth.sh -DX509_CERT_DIR=$X509_CERT_DIR -DX509_USER_PROXY=/tmp/x509up_u2574 -cp $GSILIBS:$FDTJAR:$AUTHCLIENTJAR authenticator.AuthClient -p 9000 -h gridftp01.ultralight.org -u AuthClient-file_remote_user_name-%(numTest)s 2>&1 AuthClient-output-%(numTest)s.log &"

outputFile = "AuthClient_runner.sh"

f = open(outputFile, 'w')
f.write("source ../fdtd-system-conf.sh\n\n")
print "creating '%s' file ..." % outputFile
for i in range(1, NUMTESTS + 1):
    t = TEMPLATE % { "numTest": "%03d" % i }
    print t
    f.write("%s\n" % t)
f.close()