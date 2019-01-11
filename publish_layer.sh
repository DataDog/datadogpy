#!/bin/bash

# This script will publish the datadogpy layer across regions, using the AWS CLI
# Usage: publish_layer.sh [region]
# Specifying the region arg will publish the layer for the single specified region

PYTHON_VERSIONS_FOR_AWS_CLI=("python2.7" "python3.6" "python3.7")
LAYER_PATHS=("./layers/datadogpy27.zip" "./layers/datadogpy36.zip" "./layers/datadogpy37.zip")
LAYER_NAMES=("Datadog-Python27-metric" "Datadog-Python36-metric" "Datadog-Python37-metric")

AVAILABLE_REGIONS=(us-east-2 us-east-1 us-west-1 us-west-2 ap-south-1 ap-northeast-3 ap-northeast-2 ap-southeast-1 ap-southeast-2 ap-northeast-1 ca-central-1  eu-central-1 eu-west-1 eu-west-2 eu-west-3 sa-east-1)
# (us-gov-east-1 us-gov-west-1 cn-north-1 cn-northwest-1) not supported yet

# Check that the layer files exist
for layer_file in "${LAYER_PATHS[@]}"
do
    if [ ! -f $layer_file  ]; then
        echo "Could not find $layer_file."
        exit 1
    fi
done

# Check region arg
if [ -z "$1" ]; then
    echo "Region parameter not specified, running for all available regions."
    REGIONS=("${AVAILABLE_REGIONS[@]}")
else
    echo "Region parameter specified: $1"
    if [[ ! " ${AVAILABLE_REGIONS[@]} " =~ " ${1} " ]]; then
        echo "Could not find $1 in available regions: ${AVAILABLE_REGIONS[@]}"
        echo ""
        echo "EXITING SCRIPT."
        exit 1
    fi
    REGIONS=($1)
fi

echo "Starting publishing layers for regions: ${REGIONS[*]}"

for region in "${REGIONS[@]}"
do
    echo "Starting publishing layer for region $region..."

    # Publish the layers for each version of python
    i=0
    for layer_name in "${LAYER_NAMES[@]}"; do
        aws_version_key="${PYTHON_VERSIONS_FOR_AWS_CLI[$i]}"
        layer_path="${LAYER_PATHS[$i]}"

        # After the beta we should use this instead of s3 buckets:
        # aws lambda publish-layer-version --content ZipFile=$LAYER_FILE...
        version_nbr=$(aws lambda publish-layer-version --layer-name $layer_name \
            --description "Datadog python API client for lambdas" \
            --zip-file "fileb://$layer_path" \
            --region $region \
            --compatible-runtimes $aws_version_key \
                          | jq -r '.Version')


        aws lambda add-layer-version-permission --layer-name $layer_name \
            --version-number $version_nbr \
            --statement-id "release-$version_nbr" \
            --action lambda:GetLayerVersion --principal "*" \
            --region $region

        # TODO: Add other public permissions when AWS CLI supports them

        echo "Published layer for region $region, python version $aws_version_key, layer_name $layer_name, layer_version $version_nbr"

        i=$(expr $i + 1)

    done

done

echo "Done !"
