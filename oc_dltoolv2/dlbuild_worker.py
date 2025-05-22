import argparse
import logging
import os
import time
from oc_dlinterface.dlbuild_worker_interface import DLBuildQueueServer
from oc_logging.Logging import setup_logging
from oc_cdtapi import PgQAPI


class DLBuildWorker(DLBuildQueueServer):

    def custom_connect(self):
        logging.debug('Reached DLBuildWorker.connect')
        self.pgq = PgQAPI.PgQAPI()
        logging.debug('self.pgq: [%s]' % self.pgq)

    def custom_run(self):
        logging.debug('Reached DLBuildWorker.run')
        msg = None
        process_status = None
        err_message = None
        while True:
            tag = None
            ds = self.pgq.new_msg_from_queue('cdt.dlbuild.input')
            if not ds:
                logging.debug('No new messages, sleeping [%s] seconds' % self.sleep)
                time.sleep(int(self.sleep))
                continue

            msg, msg_id = ds
            logging.debug('new_msg_from_queue id [%s] is [%s]' % (msg_id, msg) )

            try:
                tag = msg[1][0]
            except:
                logging.error('inconsistent message [%s] in queue' % msg)
                continue

            if not tag:
                logging_error('failed to fetch tag from message [%s]' % msg)
                continue

            logging.debug('fetched tag: [%s]' % tag)
            process_status, err_message = self.try_build_delivery(tag, msg_id)
            if process_status:
                logging.info('process status: [%s]' % process_status)
                logging.info('err message: [%s]' % err_message)
                self.finish_msg_prc(msg_id, process_status, err_message)
            else:
                logging.error('No process status returned, assuming message [%s] is marked as failed' % msg_id)

    def finish_msg_prc(self, msg_id, process_status, err_message):
        logging.debug('reached finish_msg_prc')
        if process_status in ['OK', 'WARNING']:
            self.pgq.msg_proc_end(msg_id, comment_text=err_message)
        else:
            self.pgq.msg_proc_fail(msg_id, error_message=err_message)

    def try_build_delivery(self, tag, msg_id):
        logging.debug('Reached try_build_delivery')
        logging.debug('Will try to build delivery for tag [%s]' % tag)
        # TODO check type of received parameter
        process_status = None
        err_message = None
        try:
            process_status, err_message = self.build_delivery(tag)
        except Exception as e:
            logging.exception('Delivery build failed: %s' % e)
            self.pgq.msg_proc_fail(msg_id, error_message=str(e))
        return process_status, err_message

    def __init__(self, *args, **kwargs):
        setup_logging()
        self.mail_config_file = None
        self.msg_source = None
        self._kwargs = kwargs.copy()
        logging.debug('Reached DLBuildWorker __init__')
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
        exit_status = None
        exit_message = None
        for process_status in process_status_list:
            if process_status.process == 'build_process':
                exit_status = process_status.status
                exit_message = process_status.errmsg
            message = "Subprocess \"%s\" finished with status %s" % (process_status.process, process_status.status)
            if process_status.status == "OK":
                logging.debug(message)
            else:
                err_message = "; The error is: '%s' (%s)" % (process_status.errmsg, process_status.exception)
                logging.error(message + err_message)

        logging.info("Build process completed for tag %s", delivery_tag)
        return exit_status, exit_message

    def init(self, args):
        logging.debug('Reached DLBuildWorker.init')
        self.sleep = args.sleep
        if args.mail_config_file is not None:
            self.mail_config_file = os.path.abspath(args.mail_config_file)
            logging.debug('set self.mail_config_file to [%s]' % self.mail_config_file)
        else:
            self.mail_config_file = None
        if args.msg_source is not None:
            self.msg_source = args.msg_source
            logging.debug('set self.msg_source to [%s]' % self.msg_source)
        else:
            self.msg_source = None
        if self.msg_source == 'db':
            logging.info('Message source is database, overriding base connect and run methods')
            logging.warn('Disregard following message about queues connection. It will be moved to proper method later')
            self.connect = self.custom_connect
            self.run = self.custom_run

    def custom_args(self, parser):
        logging.debug('Reached DLBuildWorker.custom_args')
        parser.add_argument("--mail-config-file", dest="mail_config_file", help="Mailer configuration file", default=os.getenv("MAIL_CONFIG_FILE"))
        parser.add_argument("--msg_source", dest="msg_source", help="The source of messages - amqp or db", default=os.getenv("MSG_SOURCE"))
        parser.add_argument("--sleep", dest="sleep", help="Seconds between new messages queries", default="10")

    def prepare_parser(self):
        logging.debug('Reached DLBuildWorker.prepare_parser')
        return argparse.ArgumentParser(description='Delivery build worker')


if __name__ == '__main__':
    logging.debug("Starting DLBuildWorker main loop")
    exit(DLBuildWorker().main())
