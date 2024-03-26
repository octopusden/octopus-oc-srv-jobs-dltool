import logging
import os
from oc_dlinterface.dlbuild_worker_interface import DLBuildQueueServer


class DLBuildWorker(DLBuildQueueServer):

    def __init__(self, *args, **kwargs):
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
            self._build_process = BuildProcess(api_check=api_check_enabled, **self._kwargs)

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
        return

    def custom_args(self, parser):
        """
        Append specific arguments for this worker
        :param argparse.ArgumentParser parser: parser with arguments
        :return argparse.ArgumentParse: modified parser with additional arguments
        """

        ### SMTP (mailer) arguments
        parser.add_argument("--mail-config-file", dest="mail_config_file", help="Mailer configuration file",
                            default=os.getenv("MAIL_CONFIG_FILE"))

        return parser


if __name__ == '__main__':
    exit(DLBuildWorker().main())
