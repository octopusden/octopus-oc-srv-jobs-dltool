# Delivery Builder Worker.

## Proceeding principles.
- Listens to *cdt.dlbuild.input* queue for build requests. Queue may be re-defined.
- Gets delivery data from *Subversion* link specified in the request.
- Builds delivery using *Subversion* and *Maven* sources.
- Registers files used for build in delivery database by means of queue requests (*cdt.dlcontents.input/cdt.dlartifacts.input*)
- Saves final delivery to Maven.
- Sends requests to (*cdt.dlcontents.input/cdt.dlartifacts.input*) for registering delivery and its contents.

This job is responsible for wrapping (obfuscating) SQL code using Oracle wrap utility - if specified in the source.

## Installation.

`python -m pip install oc-dltool`

## Running

`python -m oc_dltool`

## Short arguments description

`python -m oc_dltool --help`
