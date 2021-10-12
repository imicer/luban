#!/bin/bash



OFFLINEDIR=$1
CASE_PACKAGE_NAME=$2
PRIVATE_REGISTRY=$3
CPD_OPERATORS_NAMESPACE=$4
CPD_INSTANCE_NAMESPACE=$5
CPD_LICENSE=$6
STORAGE_TYPE=$7
STORAGE_CLASS=$8

# # Clone yaml files from the templates
unalias cp
cp ./templates/cpd/wsl-sub.yaml wsl-sub.yaml
cp ./templates/cpd/wsl-cr.yaml wsl-cr.yaml

# Create wsl catalog source 

echo '*** executing **** create Cloud Pak for Data Platform (zen) catalog source'

cloudctl case launch \
  --case ${OFFLINEDIR}/${CASE_PACKAGE_NAME} \
  --inventory wslSetup \
  --namespace openshift-marketplace \
  --action install-catalog \
  --args "--registry ${PRIVATE_REGISTRY} --inputDir ${OFFLINEDIR} --recursive"


sleep 1m

# Install wsl operator 

sed -i -e s#CPD_OPERATORS_NAMESPACE#${CPD_OPERATORS_NAMESPACE}#g wsl-sub.yaml

echo '*** executing **** oc create -f wsl-sub.yaml'
result=$(oc apply -f wsl-sub.yaml)
echo $result
sleep 1m


# Checking if the wsl operator pods are ready and running. 

./pod-status-check.sh ibm-cpd-ws-operator ${CPD_OPERATORS_NAMESPACE}

# switch zen namespace

oc project ${CPD_INSTANCE_NAMESPACE}

# Create wsl CR: 
sed -i -e s#CPD_INSTANCE_NAMESPACE#${CPD_INSTANCE_NAMESPACE}#g wsl-cr.yaml
sed -i -e s#CPD_LICENSE#${CPD_LICENSE}#g wsl-cr.yaml
sed -i -e s#STORAGE_TYPE#${STORAGE_TYPE}#g wsl-cr.yaml
sed -i -e s#STORAGE_CLASS#${STORAGE_CLASS}#g wsl-cr.yaml
if [ " $STORAGE_TYPE" == "nfs" ] | [ " $STORAGE_TYPE" == "ibm-spectrum-scale-sc" ]
then
echo "Remove the storageVendor option"
sed '/storageVendor/d' wsl-cr.yaml
fi

result=$(oc apply -f wsl-cr.yaml)
echo $result

# check the WSL cr status

./check-cr-status.sh ws ws-cr ${CPD_INSTANCE_NAMESPACE} wsStatus