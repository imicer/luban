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
cp ./templates/cpd/cpd-operator-group.yaml cpd-operator-group.yaml
cp ./templates/cpd/cpd-operator-sub.yaml cpd-operator-sub.yaml
cp ./templates/cpd/cpd-operators-namespace-scope.yaml cpd-operators-namespace-scope.yaml

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

oc patch NamespaceScope cpd-operators -n ${CPD_OPERATORS_NAMESPACE} --type=merge --patch='{"spec": {"csvInjector": {"enable": true} } }'


sed -i -e s#CPD_OPERATORS_NAMESPACE#${CPD_OPERATORS_NAMESPACE}#g cpd-operator-sub.yaml
echo '*** executing **** oc apply -f cpd-operator-sub.yaml'
result=$(oc apply -f cpd-operator-sub.yaml)
echo $result
sleep 60

while true; do
if oc get sub -n ${CPD_OPERATORS_NAMESPACE} cpd-operator -o jsonpath='{.status.installedCSV} {"\n"}' | grep cpd-platform-operator.v2.0.3 >/dev/null 2>&1; then
  echo -e "\ncpd-platform-operator.v2.0.3 was successfully created."
  break
fi
sleep 10
done

while true; do
if oc get csv -n ${CPD_OPERATORS_NAMESPACE} cpd-platform-operator.v2.0.3 -o jsonpath='{ .status.phase } : { .status.message} {"\n"}' | grep "Succeeded : install strategy completed with no errors" >/dev/null 2>&1; then
  echo -e "\nInstall strategy completed with no errors"
  break
fi
sleep 10
done

while true; do
if oc get deployments -n ${CPD_OPERATORS_NAMESPACE} -l olm.owner="cpd-platform-operator.v2.0.3" -o jsonpath="{.items[0].status.availableReplicas} {'\n'}" | grep 1 >/dev/null 2>&1; then
  echo -e "\ncpd-platform-operator.v2.0.3 is ready."
  break
fi
sleep 10
done

while true; do
if oc get pods -n ${CPD_OPERATORS_NAMESPACE} | grep cpd-platform-operator-manager >/dev/null 2>&1; then
  echo -e "\ncpd-platform-operator-manager pods running"
  break
fi
sleep 10
done


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
sed -i -e s#CPD_LICENSE#${CPD_LICENSE}#g zen-lite-cr.
sed -i -e s#STORAGE_CLASS#${STORAGE_CLASS}#g zen-lite-cr.yaml
sed -i -e s#ZEN_CORE_METADB_STORAGE_CLASS#${ZEN_CORE_METADB_STORAGE_CLASS}#g zen-lite-cr.yaml
echo '*** executing **** oc apply -f zen-lite-cr.yaml'
result=$(oc apply -f zen-lite-cr.yaml)
echo $result

# check if the zen operator pod is up and running.

./pod-status-check.sh ibm-zen-operator ${CPD_OPERATORS_NAMESPACE}
./pod-status-check.sh ibm-cert-manager-operator ${CPD_OPERATORS_NAMESPACE}

./pod-status-check.sh cert-manager-cainjector ${CPD_OPERATORS_NAMESPACE}
./pod-status-check.sh cert-manager-controller ${CPD_OPERATORS_NAMESPACE}
./pod-status-check.sh cert-manager-webhook ${CPD_OPERATORS_NAMESPACE}

# check the lite cr status

./check-cr-status.sh ibmcpd ibmcpd-cr ${NAMESPACE} controlPlaneStatus