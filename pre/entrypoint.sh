#!/bin/bash
# Install extra deps from /opt/extra-deps.txt if it exists
if [ -f /opt/extra-dependencies.txt ]; then
    pip install -r /opt/extra-dependencies.txt
fi
cd /opt/pipelines/

python3 -u main.py -c /opt/pipelines/pipelines.conf
