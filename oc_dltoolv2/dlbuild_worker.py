import logging
import os
from oc_dlinterface.dlbuild_worker_interface import DLBuildQueueServer
from oc_dltoolv2.build_delivery_from_queue import BuildProcess


class DLBuildWorker(DLBuildQueueServer):

    def __init__(self, *args, **kwargs):
        logging.basicConfig(level=logging.DEBUG)
        api_check_enabled = (os.getenv("DISTRIBUTIVES_API_CHECK_ENABLED", 'false').lower() in ["true", "yes"])
        self.build_process = BuildProcess(api_check=api_check_enabled, **kwargs)
        super(DLBuildWorker, self).__init__()

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


if __name__ == '__main__':
    exit(DLBuildWorker().main())
