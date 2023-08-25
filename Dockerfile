FROM python:3.10-slim-bullseye
MAINTAINER LibertyAces Ltd
LABEL "space.bitswan.pipeline.protocol-version"="2023.8-1"

RUN set -ex \
	&& apt-get -y update \
	&& apt-get -y upgrade

# RUN set -ex \
# 	&& apt-get -y install lsof

RUN apt-get -y install \
	git \
	gcc \
	g++ \
	libsnappy-dev

COPY . /app/
RUN cd /app/ ; pip3 install .

FROM python:3.10-slim-bullseye
MAINTAINER LibertyAces Ltd

COPY --from=0 /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

EXPOSE 80/tcp

CMD ["python3", "-m", "bspump", "-w"]
