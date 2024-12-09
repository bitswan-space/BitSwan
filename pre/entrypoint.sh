#!/bin/bash
# Install extra deps from /opt/extra-deps.txt if it exists
if [ -f /opt/pipelines/extra-dependencies.txt ]; then
    pip install -r /opt/pipelines/extra-dependencies.txt
fi
cd /opt/

python3 -u main.py -c /opt/pipelines/pipelines.conf
