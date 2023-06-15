import argparse
import logging
import traceback
import os
from collections import namedtuple

from oc_cdtapi.NexusAPI import parse_gav
from oc_connections.ConnectionManager import ConnectionManager

#from cdt.connections.ORMConfigurator import configure_django_orm
from oc_orm_initializator.orm_initializator import OrmInitializator
from oc_checksumsq.checksums_interface import ChecksumsQueueClient
from oc_delivery_apps.dlmanager.DLModels import DeliveryList, InvalidPathError
from fs.tempfs import TempFS

import oc_dltoolv2.DeliveryChannels as DeliveryChannels
from oc_dltoolv2.errors import BuildError
from oc_dltoolv2.notifications import AutoSetupNotificator
from oc_dltoolv2.distributives_api_client import DistributivesAPIClient

from oc_dltoolv2.delivery_artifacts_checker import DeliveryArtifactsChecker


class BuildProcess(object):

    def __init__(self, *args, **kvargs):
        self.conn_mgr = kvargs.pop('conn_mgr', ConnectionManager())
        self.setup_orm = kvargs.pop('setup_orm', True)
        if kvargs.pop('api_check', False):
            self.distributives_api_client = DistributivesAPIClient()
        else:
            self.distributives_api_client = None
        
        self.amqp_exchange = os.getenv("AMQP_EXCHANGE", "cdt.dlartifacts.input")

        # self.registration_client.basic_args(self.parser)  # add AMQP-specific arguments

        if self.setup_orm:
            #configure_django_orm(self.conn_mgr, INSTALLED_APPS=[
            #    "dlmanager", "django.contrib.auth", "django.contrib.contenttypes"])
            OrmInitializator(installed_apps = ['dlmanager'])

    def get_target_delivery_params(self, tag):
        """ Retrieve delivery params from delivery tag
        :param tag: URL of tag to read
        :return: dict of delivery attributes (keys are equal to db model fields) """
        clients_repo = self.conn_mgr.get_url("SVN_CLIENTS")
        channel = DeliveryChannels.SvnDeliveryChannel(
            clients_repo, self.conn_mgr.get_svn_client("SVN"))
        delivery_params = channel.read_delivery_at_branch(tag)
        return delivery_params

    def build_process(self, delivery_params):
        """
        Build process pipeline
        :param delivery_params: parsed params from url or tag
        """
        try:
            # originated from delivery_info.txt in SVN tag. DeliveryList is a django-ORM model
            delivery_list = DeliveryList(
                delivery_params["mf_delivery_files_specified"])
        except InvalidPathError as ipe:
            raise BuildError("Invalid path in delivery list: " + str(ipe))
        gav_str = "%s:%s:%s:zip" % tuple(
            delivery_params[key] for key in  # GAV gets created in Delivery Wizard and saved to delivery_info.txt
            ["groupid", "artifactid", "version"])
        gav = parse_gav(gav_str)

        from build_steps import BuildContext, collect_sources, calculate_and_check_checksums, build_delivery, upload_delivery
        from db_steps import save_delivery_to_db, delivery_is_in_db

        if delivery_is_in_db(delivery_params):
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
                DeliveryArtifactsChecker(delivery_params).check_artifacts_included(resources)

            archive_path = build_delivery(resources, delivery_params, context)
            upload_delivery(archive_path, gav, context)
            delivery = save_delivery_to_db(delivery_params, resources, context)
            logging.debug("Delivery was saved to database: " + delivery.gav)

            # even if checksums registration will fail, delivery will still be created
            registration_process_res = self.registration_process(
                    delivery, resources, workdir_fs, archive_path, gav, checksums_list)
            return registration_process_res

            # return (mail_result, reg_result)

    def build_delivery_from_tag(self, requested_tag=None):

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
            traceback.print_exc()
            build_exception = exc

        notify_res = self.notify_client(delivery_params, build_exception)
        build_res = [registration_process_res, notify_res]
        if build_exception:
            logging.error("Build failed for tag %s" % requested_tag)
            raise build_exception
        else:
            logging.info("Build successful for tag %s" % requested_tag)
            return build_res

    def registration_process(self, delivery, resources, workdir_fs, archive_path, gav, checksums_list):
        from register import register_delivery_content, register_delivery_resource
        registration_client = ChecksumsQueueClient()
        parser = argparse.ArgumentParser(
            description="This script launches build process for delivery specified by groupid:artifactid:version")
        default_args = registration_client.basic_args(parser).parse_args()
        default_args.exchange = self.amqp_exchange
        # Set max priority for messages from dltool
        default_args.priority = 3
        registration_client.setup_from_args(default_args)
        try:
            registration_client.connect()  # should be called just before sending message
            for resource in resources:
                register_delivery_resource(resource, registration_client, checksums_list)
            register_delivery_content(
                workdir_fs, archive_path, gav, registration_client)
            registration_client.disconnect()
            logging.debug("Checksums were computed for " + delivery.gav)
            return ProcessStatus("registration_process", "OK", "", None)
        except Exception as e:
            logging.error("An error occured during checksums registration for " + delivery.gav + repr(e))
            return ProcessStatus("registration_process", "FAILED", repr(e), e)

    def notify_client(self, delivery_params, build_exception):
        recipient = '@'.join([delivery_params["mf_delivery_author"], os.getenv("MAIL_DOMAIN")])
        gav = {"g": delivery_params["groupid"], "a": delivery_params["artifactid"],
               "v": delivery_params["version"]}
        try:
            with AutoSetupNotificator(conn_mgr=self.conn_mgr) as notificator:
                if not build_exception or isinstance(build_exception, PreparedDeliveryProcessingError):
                    notificator.send_success_notification(recipient, gav)
                    return ProcessStatus("notify_client", "OK", "", None)

        except Exception as e:  # TODO: replace with Notificator/MailerException
            # ignore errors raised by notification
            logging.error("An error occured on notification send" + repr(e))
            return ProcessStatus("notify_client", "FAILED", repr(e), e)


class PreparedDeliveryProcessingError(Exception):
    pass


class MailSendError(Exception):
    pass


ProcessStatus = namedtuple("ProcessStatus", "process status errmsg exception")
