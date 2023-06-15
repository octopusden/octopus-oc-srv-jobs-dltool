ARG PYTHON_VERSION="3.7"
FROM python:${PYTHON_VERSION}

USER root
RUN rm -rf /build
RUN apt-get -y update && apt-get -y install python3-pysvn python3-pip

COPY --chown=root:root . /build
WORKDIR /build

RUN /usr/bin/python3 -m pip install $(pwd) 
RUN /usr/bin/python3 -m unittest discover -v 
RUN /usr/bin/python3 setup.py bdist_wheel

CMD python3 dltoolv2/dlbuild_worker.py --reconnect-tries 5
