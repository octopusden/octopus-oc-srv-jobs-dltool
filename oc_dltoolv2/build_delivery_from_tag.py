import os
import argparse
import logging
import traceback

from oc_cdtapi.NexusAPI import parse_gav
from cdt.connections.ConnectionManager import ConnectionManager
from cdt.connections.ORMConfigurator import configure_django_orm
from cdt_checksumsq.checksums_interface import ChecksumsQueueClient
from dlmanager.DLModels import DeliveryList, InvalidPathError
from fs.tempfs import TempFS

from oc_dltoolv2 import DeliveryChannels
from errors import BuildError
from notifications import AutoSetupNotificator

logger = logging.getLogger(__name__)


def get_target_delivery_params(tag, conn_mgr):
    """ Retrieve delivery params from delivery tag 
    :param tag: URL of tag to read
    :return: dict of delivery attributes (keys are equal to db model fields) """
    clients_repo = conn_mgr.get_url("SVN_CLIENTS")
    channel = DeliveryChannels.SvnDeliveryChannel(
        clients_repo, conn_mgr.get_svn_client("SVN"))
    delivery_params = channel.read_delivery_at_branch(tag)
    return delivery_params


def build_process(delivery_params, registration_client):
    """
    Build process pipeline
    :param delivery_params: parsed params from url or tag
    :param registration_client: entity of ChecksumsQueueClient()
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
    conn_mgr = ConnectionManager()

    # django setup is required, so import these steps here
    configure_django_orm(conn_mgr, INSTALLED_APPS=[
        "dlmanager", "django.contrib.auth", "django.contrib.contenttypes"])
    from build_steps import BuildContext, collect_sources, build_delivery, upload_delivery
    from db_steps import save_delivery_to_db
    from register import register_delivery_content, register_delivery_resource

    # exceptions at single steps are not processed - they should stop build process
    with TempFS(temp_dir=".") as workdir_fs:
        # BuildContext is just a NamedTuple that has workdir_fs and conn_mgr
        context = BuildContext(workdir_fs, conn_mgr)
        resources = collect_sources(
            delivery_params["mf_tag_svn"], delivery_list, context)
        archive_path = build_delivery(resources, delivery_params, context)
        upload_delivery(archive_path, gav, context)

        delivery = save_delivery_to_db(delivery_params, resources, context)
        logger.info("Delivery was saved to database: " + delivery.gav)

        # even if checksums registration will fail, delivery will still be created
        try:
            registration_client.connect()  # should be called just before sending message
            for resource in resources:
                register_delivery_resource(resource, registration_client)
            register_delivery_content(
                workdir_fs, archive_path, gav, registration_client)
            logger.info("Checksums were computed")
        except:
            logger.exception("An error occured after delivery preparation")
            raise PreparedDeliveryProcessingError(
                "Delivery postprocessing has failed")


class PreparedDeliveryProcessingError(Exception):
    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="This script launches build process for delivery specified by groupid:artifactid:version")
    parser.add_argument("-t", "--delivery_tag",
                        help="Delivery tag url", required=True)
    parser.add_argument("-j", "--job_name",
                        help="Build job name", required=False)
    parser.add_argument("-b", "--build_num",
                        help="Build number", required=False)
    parser.add_argument("-v", "--verbose",
                        help="Set logging level to INFO", action="store_true")

    registration_client = ChecksumsQueueClient()
    registration_client.basic_args(parser)  # add AMQP-specific arguments

    args = parser.parse_args()

    registration_client.setup_from_args(args)  # setup AMQP-specific parameters

    if args.verbose:
        logging_level = logging.DEBUG
    else:
        logging_level = logging.WARNING
    logging.basicConfig(level=logging_level)
    logging.getLogger("requests").setLevel(logging.WARNING)

    tag = args.delivery_tag
    build_params = {"mf_ci_job": args.job_name, "mf_ci_build": args.build_num}
    # don't send notification if delivery params read has failed - we don't know the recipient
    # knows nearly everything about connections to external services like mvn, svn, ...
    conn_mgr = ConnectionManager()
    delivery_params = get_target_delivery_params(
        tag, conn_mgr)  # read delivery_info.txt from SVN
    # added build number and job name from CI to delivery info
    delivery_params.update(build_params)

    try:
        build_process(delivery_params, registration_client)
        build_exception = None
    except Exception as exc:
        traceback.print_exc()
        build_exception = exc

    recipient = '@'.join([delivery_params["mf_delivery_author"], os.getenv("MAIL_DOMAIN")])
    gav = {"g": delivery_params["groupid"], "a": delivery_params["artifactid"],
           "v": delivery_params["version"]}
    try:
        with AutoSetupNotificator() as notificator:
            if not build_exception or isinstance(build_exception, PreparedDeliveryProcessingError):
                notificator.send_success_notification(recipient, gav)
            else:
                notificator.send_failure_notification(
                    recipient, gav, args.job_name, args.build_num)
    except Exception as notify_exc:  # TODO: replace with Notificator/MailerException
        # ignore errors raised by notification
        logger.exception("An error occured on notification send")

    # raise build exception only after notification attempt
    if build_exception:
        raise build_exception
