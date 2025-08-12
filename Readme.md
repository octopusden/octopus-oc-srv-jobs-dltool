# Delivery Builder Worker.

## Proceeding principles.
- Listens to *cdt.dlbuild.input* queue or checks queue\_message in postgres for build requests. Queue may be re-defined.
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

## Runtime settings:

Most of them are done via environment variables and several only can be re-defined from command line arguments.

**NOTE**: *AMQP* queue is now hardcoded to *cdt.dlbuild.input* and may not be redefined for now.

- *ORACLE\_HOME* - folder where Oracle database is installed. Necessary for *wrap* functionality to work. *Oracle wrap* binary is to be then at path `${ORACLE_HOME}/bin/wrap`
- *PSQL\_URL*, *PSQL\_USER*, *PSQL\_PASSWORD* - credentials for *PostgerSQL* database connection, used for *Django* models. *PSQL_URL* should contan database schema as a parameter. Format: `{hostFQDN}:{port}/{instance}?search_path={schema}`
- *AMQP\_URL*, *AMQP\_USER*, *AMQP\_PASSWORD* - credentials for queue connection (*RabbitMQ* or other *AMQP* implementation)
- *SMTP\_URL*, *SMTP\_USER*, *SMTP\_PASSWORD* - credentials for mail server *SMTP* protocol - to send an e-mail notifications to delivery authors about delivery being ready.
- *SVN\_CLIENTS\_URL*, *SVN\_CLIENTS\_USER*, *SVN\_CLIENTS\_PASSWORD* - credentials for SubVersion section of clients-related data.
- *MVN\_URL*, *MVN\_USER*, *MVN\_PASSWORD* - credentials for maven-like repository connection (*Sontatype Nexus* and *JFrog Artifactory* are currently supported only)
- *MVN\_DOWNLOAD\_REPO* - *Maven* repository to download delivery components from
- *MVN\_UPLOAD\_REPO* - *Maven* repository to upload packed deliveries to
- *MVN\_PREFIX* - *GroupID* prefix for packed delivery *GAV*.
- *MVN\_RN\_SUFFIX* - Release Notes *GroupID* suffix for *GAV*. Necessary for Release Notes auto-append.
- *MVN\_DOC\_SUFFIX* - Documentation *GroupID* suffix for *GAV*. Necessary for Documentation auto-append.
- *PSQL\_MQ\_URL* - postgres url for mq scheme
- *PSQL\_MQ\_USER* - postgres username for mq scheme
- *PSQL\_MQ\_PASSWORD* - postgres password for mq scheme
- *DELIVERY\_PORTAL\_URL* - URL for delivery-tool web-interface to see delivery information, used for e-mail notification.
- *PORTAL\_RELEASE\_NOTES\_ENABLED* - enable or disable appending *Release Notes*. Default: `"False"`
- *DISTRIBUTIVES\_API\_CHECK\_ENABLED* - enable or disable check if distributives included to the delivery are deliverable. Default: `"False"`
- *DISTRIBUTIVES\_API\_URL* - *URL* for *Distributives API* microservice. Mandatory if *DISTRIBUTIVES\_API\_CHECK\_ENABLED* is set to `"True"`
- *MAIL\_DOMAIN* - mail domain for notifications where delivery authors mailboxes are.
- *MAIL\_CONFIG\_FILE* - path to mailer configuration file.
- *MAIL\_CONFIG\_DIR* - path to mailer configuration directory.
- *COUNTERPARTY\_ENABLED* - enable or disable client counterparty functionality for Release Notes and Documentation appending. Default: `"False"`      
- *CLIENT\_PROVIDER\_URL* - *URL* for *Client Provider* microservice. Mandatory if *COUNTERPARTY\_ENABLED* is set to `"True"`
- *DELIVERY\_ADD\_ARTS\_PATH* - Additional *JSON*ized setting path. Used for appending *Copyright* files if necessary. Useless if *COUNTERPARTY\_ENABLED* is `"False"`
- *MSG\_SOURCE* - message source, should be either *amqp* for rabbitmq or *db* for postgres
