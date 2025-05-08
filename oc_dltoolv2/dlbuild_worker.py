import argparse
import logging
import os
from oc_dlinterface.dlbuild_worker_interface import DLBuildQueueServer
from oc_logging.Logging import setup_logging


class DLBuildWorker(DLBuildQueueServer):

    def __init__(self, *args, **kwargs):
        setup_logging()
        self.mail_config_file = None
        self._kwargs = kwargs.copy()
        kwargs.pop('setup_orm', False)
        kwargs.pop('conn_mgr', None)
        super().__init__(*args, **kwargs)

    @property
    def build_process(self):
        if not hasattr(self, '_build_process'):
            api_check_enabled = (os.getenv("DISTRIBUTIVES_API_CHECK_ENABLED", 'false').lower() in ["true", "yes"])
            logging.info("API check enabled: %s" % api_check_enabled)
            from .build_delivery_from_queue import BuildProcess
            self._build_process = BuildProcess(api_check=api_check_enabled, mail_config_file=self.mail_config_file, **self._kwargs)

        return self._build_process

    def ping(self):
        return

    def build_delivery(self, delivery_tag):
        logging.info("Received build delivery request for tag %s" % delivery_tag)
        process_status_list = self.build_process.build_delivery_from_tag(requested_tag=delivery_tag)
        for process_status in process_status_list:
            message = "Subprocess \"%s\" finished with status %s" % (process_status.process, process_status.status)
            if process_status.status == "OK":
                logging.debug(message)
            else:
                err_message = "; The error is: '%s' (%s)" % (process_status.errmsg, process_status.exception)
                logging.error(message + err_message)

        logging.info("Build process completed for tag %s", delivery_tag)
        return

    def init(self, args):
        if args.mail_config_file is not None:
            self.mail_config_file = os.path.abspath(args.mail_config_file)
        else:
            self.mail_config_file = None

    def custom_args(self, parser):
        parser.add_argument("--mail-config-file", dest="mail_config_file", help="Mailer configuration file",
                            default=os.getenv("MAIL_CONFIG_FILE"))

    def prepare_parser(self):
        return argparse.ArgumentParser(description='Delivery build worker')


if __name__ == '__main__':
    logging.debug("Starting DLBuildWorker main loop")
    exit(DLBuildWorker().main())
