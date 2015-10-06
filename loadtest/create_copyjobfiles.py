"""
* generate copyjobfiles according to the specified templated line
*
* run
    cd loadtest
    python create_copyjobfiles.py
"""

# number of copyjobfiles
# number of tests are iterated from 1
NUMTESTS = 10

# number of files per copyjobfile
NUMFILES = 10

# copyjobfile template line
TEMPLATE = "fdt://t3-fdt.ultralight.org:8444//mnt/hadoop/user/maxa/transfer_test/file_group-10x1GB/1GB-%(numFile)s.test   fdt://gridftp01.ultralight.org:8444/store/user/maxa/fdtcptests/test-%(numTest)s/1GB-%(numFile)s.test"
MD5LINE = "fdt://t3-fdt.ultralight.org:8444//mnt/hadoop/user/maxa/transfer_test/file_group-10x1GB/file_group-10x1GB.md5   fdt://gridftp01.ultralight.org:8444/store/user/maxa/fdtcptests/test-%(numTest)s/file_group-10x1GB.md5"

for i in range(1, NUMTESTS + 1):
    copyJobFileName = "copyjobfile-%03d" % i
    f = open(copyJobFileName, 'w')
    print "\n\ncreating '%s'" % copyJobFileName
    for ii in range(1, NUMFILES + 1):
        t = TEMPLATE % { "numFile": "%02d" % ii, "numTest": "%03d" % i }
        print t
        f.write("%s\n" % t)
    t = MD5LINE % { "numTest": "%03d" % i }
    print t
    f.write(t)
f.close()