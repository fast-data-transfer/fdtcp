#!/bin/sh

# deploy script for phedex-fdt (fdtcp project)

# uses rsync (doesn't seem to work well with sshfs sometimes - files are
#   copied over and synced but in case of T3 it sometimes happened they
#   didn't even existed at the destination ...)
#   --cvs-exclude looks into $HOME/.cvsignore
#   --inplace sorts out permission at destination problem (renaming failed)

# tried just copy everything over scp (and copying everything over
#   brute force seems anyway much quicker than rsync's examination)


find -name '*.pyc' -exec rm {} \;


# T3
#COMMAND="rsync --exclude-from=.hgignore -v --progress -recursive --inplace /home/xmax/tmp/caltech/phedex-fdt/fdtcp/ /mnt/t2caltech/fdtcp/"
COMMAND="scp -r -c blowfish /home/xmax/tmp/caltech/phedex-fdt/fdtcp/* maxa@t3-susy.ultralight.org:fdtcp"

echo -e "\n\n\n"
echo -e "###################################"
echo -e "job running:\n$COMMAND\n"
$COMMAND


# T2 (scp quite slow in case of T2 ...)
#COMMAND="rsync --exclude-from=.hgignore -v --progress -recursive --inplace /home/xmax/tmp/caltech/phedex-fdt/fdtcp/ /mnt/t3cern/fdtcp/"
COMMAND="scp -r -c blowfish /home/xmax/tmp/caltech/phedex-fdt/fdtcp/* maxa@t2-headnode.ultralight.org:fdtcp"


echo -e "\n\n\n"
echo -e "###################################"
echo -e "job running:\n$COMMAND\n"
$COMMAND


echo -e "\n\n\n"
echo "do 'cp wrapper_* /usr/bin' on the destination systems"
