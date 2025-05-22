FROM debian:bullseye

USER root

# "psycopg2" will not be installed correctly without 'libpq-dev' and 'build-essential'

RUN apt-get --quiet --assume-yes update && \
    apt-get --no-install-recommends --quiet --assume-yes install \
        python3-pysvn \
        python3-pip \
        python3-dev \
        libpq-dev \
        build-essential \
        libmagic1 && \
    python3 -m pip install --upgrade pip && \
    python3 -m pip install --upgrade setuptools wheel

RUN rm -rf /build
COPY --chown=root:root . /build
WORKDIR /build
RUN python3 -m pip install $(pwd) && \
    python3 -m unittest discover -v && \
    python3 setup.py bdist_wheel
#CMD tail -f /dev/null
ENTRYPOINT ["env", "python3", "-m", "oc_dltoolv2", "-vvv"]
