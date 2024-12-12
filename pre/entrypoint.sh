#!/bin/bash
# Install extra deps from /opt/extra-deps.txt if it exists
if [ -f /opt/pipelines/extra-dependencies.txt ]; then
    pip install -r /opt/pipelines/extra-dependencies.txt
fi
cd /opt/pipelines/

bitswan-cli /opt/pipelines/main.ipynb -c /opt/pipelines/pipelines.conf
