#!/bin/bash



OFFLINEDIR=$1
CASE_PACKAGE_NAME=$2

mkdir -p ./logs
touch ./logs/install_db2u.log
echo '' > ./logs/install_db2u.log

# Create Db2U catalog source 

echo '*** executing **** create Db2U catalog source' >> ./logs/install_db2u.log
#
yum install -y python2
alternatives --set python /usr/bin/python2
pip2 install pyyaml


cloudctl case launch \
  --case ${OFFLINEDIR}/${CASE_PACKAGE_NAME} \
  --inventory db2uOperatorSetup \
  --namespace openshift-marketplace \
  --action install-catalog \
    --args "--inputDir ${OFFLINEDIR} --recursive"

sleep 1m


alternatives --remove python /usr/bin/python2