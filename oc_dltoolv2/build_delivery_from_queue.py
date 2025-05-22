import logging
import os
from collections import namedtuple

from oc_cdtapi.NexusAPI import parse_gav
from oc_connections.ConnectionManager import ConnectionManager

from oc_orm_initializator.orm_initializator import OrmInitializator
import oc_checksumsq.checksums_interface
from fs.tempfs import TempFS

from .errors import BuildError
from .notifications import AutoSetupNotificator
from .distributives_api_client import DistributivesAPIClient

from .delivery_artifacts_checker import DeliveryArtifactsChecker


class BuildProcess(object):

    def __init__(self, *args, **kvargs):
        logging.debug('Reached BuildProcess.__init__')
        self.conn_mgr = kvargs.pop('conn_mgr', ConnectionManager())
        self.setup_orm = kvargs.pop('setup_orm', True)
        self.mail_config_file = kvargs.pop('mail_config_file', None)
        if kvargs.pop('api_check', False):
            self.distributives_api_client = DistributivesAPIClient()
        else:
            self.distributives_api_client = None
        
        self.amqp_exchange = os.getenv("AMQP_EXCHANGE", "cdt.dlartifacts.input")

        # self.registration_client.basic_args(self.parser)  # add AMQP-specific arguments

        if self.setup_orm:
            _c = {"PSQL_URL": None, "PSQL_USER": None, "PSQL_PASSWORD": None}

            for _k in _c.keys():
                _c[_k] = kvargs.pop(_k.lower(), "") or os.getenv(_k, "")

                if not _c[_k]:
                    raise ValueError("'%s' is mandatory" % _k)

            _installed_apps = [
                    'oc_delivery_apps.dlmanager',
                    'oc_delivery_apps.checksums']

            OrmInitializator(url=_c.get("PSQL_URL"), user=_c.get("PSQL_USER"), password=_c.get("PSQL_PASSWORD"), installed_apps=_installed_apps)
        
        # django models can be imported if django is configured only, so make it here
        from oc_delivery_apps.dlmanager.DLModels import DeliveryList, InvalidPathError
        from . import DeliveryChannels
        self._DeliveryList = DeliveryList
        self._InvalidPathError = InvalidPathError
        self._DeliveryChannels = DeliveryChannels

    def get_target_delivery_params(self, tag):
        """ Retrieve delivery params from delivery tag
        :param tag: URL of tag to read
        :return: dict of delivery attributes (keys are equal to db model fields) """
        logging.info("Starting to retrieve delivery parameters from tag: %s", tag)
        clients_repo = self.conn_mgr.get_url("SVN_CLIENTS")
        channel = self._DeliveryChannels.SvnDeliveryChannel(
            clients_repo, self.conn_mgr.get_svn_client("SVN"))
        delivery_params = channel.read_delivery_at_branch(tag)
        logging.info("Successfully retrieved delivery parameters from tag")
        return delivery_params

    def build_process(self, delivery_params):
        """
        Build process pipeline
        :param delivery_params: parsed params from url or tag
        """
        logging.info("Starting build process")
        try:
            # originated from delivery_info.txt in SVN tag. self._DeliveryList is a django-ORM model
            delivery_list = self._DeliveryList(
                delivery_params["mf_delivery_files_specified"])
        except self._InvalidPathError as ipe:
            raise BuildError(ipe)
        gav_str = "%s:%s:%s:zip" % tuple(
            delivery_params[key] for key in  # GAV gets created in Delivery Wizard and saved to delivery_info.txt
            ["groupid", "artifactid", "version"])
        gav = parse_gav(gav_str)

        from .build_steps import BuildContext, collect_sources, calculate_and_check_checksums, build_delivery, upload_delivery
        from .db_steps import save_delivery_to_db, delivery_is_in_db

        if delivery_is_in_db(delivery_params):
            logging.info("Delivery is already in DB, skipping build")
            return ProcessStatus("build_process", "WARNING", "Delivery already built and stored in DB", None)

        # exceptions at single steps are not processed - they should stop build process
        with TempFS(temp_dir=".") as workdir_fs:
            # BuildContext is just a NamedTuple that has workdir_fs and conn_mgr
            context = BuildContext(workdir_fs, self.conn_mgr)
            resources = collect_sources(
                delivery_params["mf_tag_svn"], delivery_list, context)
            if self.distributives_api_client:
                checksums_list = calculate_and_check_checksums(resources, self.distributives_api_client)
            else:
                checksums_list = None

            if os.getenv('COUNTERPARTY_ENABLED', 'false').lower() in ['true', 'yes', 'y']:
                logging.info("Checking inclusion of customer-specific artifacts")
                DeliveryArtifactsChecker(delivery_params).check_artifacts_included(resources)
            archive_path = build_delivery(resources, delivery_params, context)

            upload_delivery(archive_path, gav, context)
            delivery = save_delivery_to_db(delivery_params, resources, context)

            # even if checksums registration will fail, delivery will still be created
            logging.info("Starting registration process")
            registration_process_res = self.registration_process(
                    delivery, resources, workdir_fs, archive_path, gav, checksums_list)

            return registration_process_res

    def build_delivery_from_tag(self, requested_tag=None):
        logging.info("Starting build from tag: %s", requested_tag)

        build_params = {"mf_ci_job": "queue", "mf_ci_build": "0"}
        # don't send notification if delivery params read has failed - we don't know the recipient
        # knows nearly everything about connections to external services like mvn, svn, ...

        delivery_params = self.get_target_delivery_params(requested_tag)
        # read delivery_info.txt from SVN
        # added build number and job name from CI to delivery info
        delivery_params.update(build_params)
        registration_process_res = None
        try:
            registration_process_res = self.build_process(delivery_params)
            build_exception = None
        except Exception as exc:
            logging.exception(exc)
            build_exception = exc

        logging.info("Notifying client")
        notify_res = self.notify_client(delivery_params, build_exception)

        build_res = [registration_process_res, notify_res]

        if build_exception:
            logging.error("Build failed for tag %s" % requested_tag)
            raise build_exception
        
        logging.info("Build successful for tag %s" % requested_tag)
        return build_res

    def registration_process(self, delivery, resources, workdir_fs, archive_path, gav, checksums_list):
        from .register import register_delivery_content, register_delivery_resource
        registration_client = oc_checksumsq.checksums_interface.ChecksumsQueueClient()
        registration_client.setup(
                url=os.getenv("AMQP_URL"),
                username=os.getenv("AMQP_USER"),
                password=os.getenv("AMQP_PASSWORD"),
                routing_key=oc_checksumsq.checksums_interface.queue_name,
                queue_cnt=oc_checksumsq.checksums_interface.queue_cnt_name,
                priority=3)
        logging.info("Connecting to registration queue")
        try:
            registration_client.connect()  # should be called just before sending message

            logging.info("Registering delivery resources")
            for resource in resources:
                register_delivery_resource(resource, registration_client, checksums_list)

            logging.info("Registering delivery content")
            register_delivery_content(workdir_fs, archive_path, gav, registration_client)
            registration_client.disconnect()
        except Exception as e:
            logging.exception(e)
            return ProcessStatus("registration_process", "FAILED", repr(e), e)

        logging.info("Checksums were computed for GAV: '%s'" % delivery.gav)
        return ProcessStatus("registration_process", "OK", "", None)

    def notify_client(self, delivery_params, build_exception):
        recipient = '@'.join([delivery_params["mf_delivery_author"], os.getenv("MAIL_DOMAIN")])
        gav = {"g": delivery_params["groupid"], "a": delivery_params["artifactid"],
               "v": delivery_params["version"]}
        logging.info("Preparing to send notification to client: %s", recipient)
        try:
            with AutoSetupNotificator(conn_mgr=self.conn_mgr, mail_config_file=self.mail_config_file) as notificator:
                if not build_exception or isinstance(build_exception, PreparedDeliveryProcessingError):
                    notificator.send_success_notification(recipient, gav)

        except Exception as e:  # TODO: replace with Notificator/MailerException
            # ignore errors raised by notification
            logging.exception(e)
            return ProcessStatus("notify_client", "FAILED", repr(e), e)

        return ProcessStatus("notify_client", "OK", "", None)


class PreparedDeliveryProcessingError(Exception):
    pass


class MailSendError(Exception):
    pass


ProcessStatus = namedtuple("ProcessStatus", "process status errmsg exception")
