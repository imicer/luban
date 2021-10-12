#!/bin/bash



OFFLINEDIR=$1
CASE_PACKAGE_NAME=$2
PRIVATE_REGISTRY=$3
CPD_OPERATORS_NAMESPACE=$4
CPD_INSTANCE_NAMESPACE=$5
CPD_LICENSE=$6
STORAGE_CLASS=$7

# # Clone yaml files from the templates
unalias cp
cp ./templates/cpd/wsl-sub.yaml wsl-sub.yaml
# Install wsl operator 

sed -i -e s#OPERATOR_NAMESPACE#${OP_NAMESPACE}#g wsl-sub.yaml

echo '*** executing **** oc create -f wsl-sub.yaml'
result=$(oc create -f wsl-sub.yaml)
echo $result
sleep 1m


# Checking if the wsl operator pods are ready and running. 

./pod-status-check.sh ibm-cpd-ws-operator ${OP_NAMESPACE}

# switch zen namespace

oc project ${NAMESPACE}

# Create wsl CR: 
sed -i -e s#CPD_NAMESPACE#${NAMESPACE}#g wsl-cr.yaml
result=$(oc create -f wsl-cr.yaml)
echo $result

# check the WSL cr status

./check-cr-status.sh ws ws-cr ${NAMESPACE} wsStatus