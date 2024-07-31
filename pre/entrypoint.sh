#!/bin/bash
# Install extra deps from /opt/extra-deps.txt if it exists
if [ -f /opt/extra-dependencies.txt ]; then
    pip install -r /opt/extra-dependencies.txt
fi
cd /opt/

# If /opt/pipelines/pipelines.conf exists use it as conf file otherwise use /opt/pipelines.conf
if [ -f /opt/pipelines/pipelines.conf ]; then
    python3 -u main.py -c /opt/pipelines/pipelines.conf
else
    python3 -u main.py -c /opt/pipelines.conf
fi
