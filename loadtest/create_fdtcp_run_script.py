"""
* generates a bash script containing all fdtcp commands for loadtest
* run
    cd loadtest
    python create_copyjobfiles.py
"""

# number of tests are iterated from 1
NUMTESTS = 10

TEMPLATE = "time python ../fdtcp.py --copyjobfile=copyjobfile-%(numTest)s --report=reportfile-%(numTest)s 2>&1 > test-%(numTest)s.log &"

outputFile = "fdtcp_runner.sh"

f = open(outputFile, 'w')
print "creating '%s' file ..." % outputFile
for i in range(1, NUMTESTS + 1):
    t = TEMPLATE % { "numTest": "%03d" % i }
    print t
    f.write("%s\n" % t) 
f.close()