FROM python:3.13-slim-bookworm
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

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY . /src/

RUN apt-get remove -y python3-yaml && apt-get autoremove -y

RUN cd /src/ && uv pip install --system .

COPY pre/ /opt/

CMD ["sh", "/opt/entrypoint.sh"]

# Setup bitswan user

RUN useradd --uid 1000 --create-home bitswan
ENV HOME=/home/bitswan
USER bitswan

USER root
RUN mkdir -p /home/bitswan/work
RUN chown -R bitswan:bitswan /home/bitswan/work

