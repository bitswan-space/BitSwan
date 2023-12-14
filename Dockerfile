FROM python:3.10-slim-bullseye
MAINTAINER LibertyAces Ltd

RUN set -ex \
	&& apt-get -y update \
	&& apt-get -y upgrade

RUN apt-get -y install \
	git \
	gcc \
	g++ \
	libsnappy-dev \
  autoconf \
  automake \
  libtool \
  build-essential

COPY . /app/
RUN cd /app/ ; pip3 install .


FROM python:3.10-slim-bullseye
MAINTAINER LibertyAces Ltd
LABEL "space.bitswan.pipeline.protocol-version"="2023.12-1"
LABEL src=https://github.com/bitswan-space/BitSwanPump

COPY --from=0 /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY pre/entrypoint.sh /entrypoint.sh
COPY pre/main.py /opt/pipelines/main.py
COPY pre/main.ipynb /opt/pipelines/main.ipynb
COPY pre/pipelines.conf /conf/pipelines.conf

EXPOSE 80/tcp

CMD ["sh", "/entrypoint.sh"]
