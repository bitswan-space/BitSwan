FROM bitswan/pipeline-runtime-environment:2024-8030723658-git-22c5054
ARG DATA_MACHINE_SOURCE_PATH
ENV DATA_MACHINE_SOURCE_PATH_ENV=$DATA_MACHINE_SOURCE_PATH
COPY ${DATA_MACHINE_SOURCE_PATH_ENV} /opt/pipelines/
COPY . /opt/pipelines
RUN apt-get install -yqq \
 libpango-1.0-0 \
 libpangoft2-1.0-0 \
 chromium-driver

RUN pip3 install Jinja2 weasyprint selenium python-dotenv requests