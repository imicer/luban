#!/bin/bash


OFFLINEDIR=$1
CASE_PACKAGE_NAME=$2
PRIVATE_REGISTRY=$3
CPD_OPERATORS_NAMESPACE=$4
CPD_INSTANCE_NAMESPACE=$5
CPD_LICENSE=$6
STORAGE_CLASS=$7
ZEN_CORE_METADB_STORAGE_CLASS=$8

# # Clone yaml files from the templates
unalias cp
cp ./templates/cpd/bedrock-operator-group.yaml bedrock-operator-group.yaml

# Create zen catalog source 

echo '*** executing **** create Cloud Pak for Data Platform (zen) catalog source'

cloudctl case launch \
  --case ${OFFLINEDIR}/${CASE_PACKAGE_NAME} \
  --inventory cpdPlatformOperator \
  --namespace openshift-marketplace \
  --action install-catalog \
  --args "--registry ${PRIVATE_REGISTRY} --inputDir ${OFFLINEDIR} --recursive"


sleep 1m

# Create CPD Operators namespace
echo '*** executing **** create CPD Operators namespace '
oc new-project ${CPD_OPERATORS_NAMESPACE}
oc project ${CPD_OPERATORS_NAMESPACE}



# Create CPD operator group: 

sed -i -e s#CPD_OPERATORS_NAMESPACE#${CPD_OPERATORS_NAMESPACE}#g cpd-operator-group.yaml

echo '*** executing **** oc apply -f cpd-operator-group.yaml'


result=$(oc apply -f cpd-operator-group.yaml)
echo $result
sleep 1m


sed -i -e s#CPD_OPERATORS_NAMESPACE#${CPD_OPERATORS_NAMESPACE}#g cpd-operator-sub.yaml
echo '*** executing **** oc apply -f cpd-operator-sub.yaml'
result=$(oc apply -f cpd-operator-sub.yaml)
echo $result
sleep 60



# Create zen namespace
echo '*** executing **** create CPD Instance namespace '
oc new-project ${CPD_INSTANCE_NAMESPACE}
oc project ${CPD_INSTANCE_NAMESPACE}


# Create NameScope in CPD Operators namespace 
echo '*** executing **** Create NameScope in CPD Operators namespace'
sed -i -e s#CPD_OPERATORS_NAMESPACE#${CPD_OPERATORS_NAMESPACE}#g cpd-operators-namespace-scope.yaml
sed -i -e s#CPD_INSTANCE_NAMESPACE#${CPD_INSTANCE_NAMESPACE}#g cpd-operators-namespace-scope.yaml
echo '*** executing **** oc apply -f cpd-operators-namespace-scope.yaml'
result=$(oc apply -f cpd-operators-namespace-scope.yaml)
echo $result
sleep 30

# Create the zen operator 
sed -i -e s#CPD_OPERATORS_NAMESPACE#${CPD_OPERATORS_NAMESPACE}#g cpd-operator-sub.yaml

echo '*** executing **** oc apply -f cpd-operator-sub.yaml'
result=$(oc apply -f cpd-operator-sub.yaml)
echo $result
sleep 30




# Create lite CR: 
sed -i -e s#CPD_INSTANCE_NAMESPACE#${CPD_INSTANCE_NAMESPACE}#g zen-lite-cr.yaml
sed -i -e s#CPD_INSTANCE_NAMESPACE#${CPD_INSTANCE_NAMESPACE}#g zen-lite-cr.
sed -i -e s#CPD_INSTANCE_NAMESPACE#${CPD_INSTANCE_NAMESPACE}#g zen-lite-cr.yaml
sed -i -e s#CPD_INSTANCE_NAMESPACE#${CPD_INSTANCE_NAMESPACE}#g zen-lite-cr.yaml
echo '*** executing **** oc create -f zen-lite-cr.yaml'
result=$(oc create -f zen-lite-cr.yaml)
echo $result

# check if the zen operator pod is up and running.

./pod-status-check.sh ibm-zen-operator ${CPD_OPERATORS_NAMESPACE}
./pod-status-check.sh ibm-cert-manager-operator ${CPD_OPERATORS_NAMESPACE}

./pod-status-check.sh cert-manager-cainjector ${CPD_OPERATORS_NAMESPACE}
./pod-status-check.sh cert-manager-controller ${CPD_OPERATORS_NAMESPACE}
./pod-status-check.sh cert-manager-webhook ${CPD_OPERATORS_NAMESPACE}

# check the lite cr status

./check-cr-status.sh ibmcpd ibmcpd-cr ${NAMESPACE} controlPlaneStatus


wget https://github.com/IBM/cloud-pak-cli/releases/latest/download/cloudctl-linux-amd64.tar.gz
wget https://github.com/IBM/cloud-pak-cli/releases/latest/download/cloudctl-linux-amd64.tar.gz.sig
tar -xvf cloudctl-linux-amd64.tar.gz -C /usr/local/bin
mv /usr/local/bin/cloudctl-linux-amd64 /usr/local/bin/cloudctl