#!/bin/bash

IMAGE_REGISTRY_URL=$1

# # Clone yaml files from the templates
unalias cp
cp ./templates/cpd/image_content_source_policy.yaml image_content_source_policy.yaml

sed -i -e s#PRIVATE_REGISTRY#${IMAGE_REGISTRY_URL}#g image_content_source_policy.yaml

echo '*** executing **** oc apply -f image_content_source_policy.yaml'
result=$(oc apply -f image_content_source_policy.yaml)
echo $result
sleep 15m