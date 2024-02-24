FROM python:3.10-slim-bullseye
MAINTAINER LibertyAces Ltd
LABEL "space.bitswan.pipeline.protocol-version"="2023.12-1"
LABEL "space.bitswan.pipeline.ide"="Jupyter"
LABEL src=https://github.com/bitswan-space/BitSwan
ENV ASABFORCECONSOLE=1
ENV PYTHONUNBUFFERED=1

RUN set -ex \
 && apt-get update \
 && apt-get -y upgrade

RUN apt-get -yqq install \
 git \
 gcc \
 g++ \
 libsnappy-dev \
 autoconf \
 automake \
 libtool \
 build-essential \
 docker-compose

COPY . /src/
RUN cd /src/ ; pip3 install .

COPY pre/ /opt/pipelines/

CMD ["sh", "/opt/pipelines/entrypoint.sh"]

# Setup jupyterlab

COPY examples/Jupyter/ /etc/notebooks/
COPY icons/*.svg /etc/icons/

ENV JUPYTER_APP_LAUNCHER_PATH /etc/jupyter_config/
COPY ./jupyter/config.yaml /etc/jupyter_config/config.yaml

USER root
RUN chmod -R 777 /etc/notebooks/ /etc/icons/ /etc/jupyter_config/

RUN echo '#!/bin/sh\n\
chown -R bitswan /mnt\n\
cp -R /ssh /home/bitswan/.ssh\n\
chown -R bitswan /home/bitswan\n\
cd /mnt\n\
su bitswan -c jupyter notebook --port=8888 --no-browser --ip=*' > /start-ide.sh

RUN chmod +x /start-ide.sh

# Setup bitswan user

RUN useradd --uid 1000 --create-home bitswan
ENV HOME=/home/bitswan
USER bitswan

USER root
RUN mkdir -p /home/bitswan/work
RUN chown -R bitswan:bitswan /home/bitswan/work

