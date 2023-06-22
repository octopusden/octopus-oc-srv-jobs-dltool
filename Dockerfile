ARG DEBIAN_RELEASE="bullseye"
FROM debian:${DEBIAN_RELEASE}

ARG PYTHON_MAJOR_VERSION="3"
ENV PYTHON_INTERPRETER="python${PYTHON_MAJOR_VERSION}"
USER root

# "psycopg2" will not be installed correctly without 'libpq-dev' and 'build-essential'

RUN apt-get --quiet --assume-yes update && \
    apt-get --no-install-recommends --quiet --assume-yes install \
        ${PYTHON_INTERPRETER}-pysvn \
        ${PYTHON_INTERPRETER}-pip \
        ${PYTHON_INTERPRETER}-dev \
        libpq-dev \
        build-essential \
        libmagic1 && \
    ${PYTHON_INTERPRETER} -m pip install --upgrade pip && \
    ${PYTHON_INTERPRETER} -m pip install --upgrade setuptools wheel

RUN rm -rf /build
COPY --chown=root:root . /build
WORKDIR /build
RUN ${PYTHON_INTERPRETER} -m pip install $(pwd) && \
    ${PYTHON_INTERPRETER} -m unittest discover -v && \
    ${PYTHON_INTERPRETER} setup.py bdist_wheel
ENTRYPOINT ["env", "${PYTHON_INTERPRETER}", "-m", "oc_dltoolv2"]
