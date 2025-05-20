from oc_cdtapi.NexusAPI import gav_to_str
from oc_mailer.Mailer import Mailer
from oc_connections.ConnectionManager import ConnectionManager
import os


class Notificator(object):
    """
    Class for sending notifications
    """

    def __init__(self, mailer, portal_url, ci_url):
        self.mailer = mailer
        self.portal_url = portal_url
        self.ci_url = ci_url

    def send_success_notification(self, recipient, gav):
        gav_text = gav_to_str(gav)
        subject = "Delivery %s has been built successfully" % gav_text
        portal_link = self._get_portal_link(gav)
        portal_href = _create_href(portal_link, "Delivery Portal")
        text = """
        Delivery <b>%s</b> was built successfully.
        You can see details and send delivery to client at %s.
        """ % (gav_text, portal_href,)
        self._send(recipient, subject, text)

    def send_failure_notification(self, recipient, gav, job_name, build_number):
        gav_text = gav_to_str(gav)
        subject = "Build for delivery %s has failed" % gav_text
        text = """
        Build for delivery <b>%s</b> <font color="red">has failed</font>.
        """ % gav_text
        self._send(recipient, subject, text)

    def _send(self, recipient, subject, text):
        self.mailer.send_email(to_addresses=[recipient, ], subject=subject, text=text)

    def _get_console_log_link(self, job_name, build_number):
        return "%s/job/%s/%s/console" % (self.ci_url, job_name, build_number)

    def _get_portal_link(self, gav):
        return '%s/dl/details_by_gav/%s/%s/%s' % (self.portal_url, gav["g"], gav["a"], gav["v"])


class AutoSetupNotificator(object):
    """
    Sets up properties for smtp interchange
    """

    def __init__(self, conn_mgr=None, mail_config_file=None):
        self.mail_config_file = mail_config_file
        if conn_mgr is None:
            self.conn_mgr = ConnectionManager()
        else:
            self.conn_mgr = conn_mgr

    def __enter__(self):
        conn_mgr = self.conn_mgr
        smtp_user = conn_mgr.get_credential(full_name="SMTP_USER")
        self.smtp_client = conn_mgr.get_smtp_connection()
        mail_from = '@'.join([smtp_user, os.getenv("MAIL_DOMAIN") ])

        mailer = Mailer(self.smtp_client, mail_from, config_path=self.mail_config_file, template_type="html")

        portal_url = conn_mgr.get_url("DELIVERY_PORTAL")
        notificator = Notificator(mailer, portal_url, None)
        return notificator

    def __exit__(self, exception_type, exception_value, traceback):
        self.smtp_client.quit()


def _create_href(target_url, text):
    return '<a href="%s">%s</a>' % (_add_protocol(target_url), text)


def _add_protocol(url):
    # outlook gives warning for urls like host:port without protocol, so add it if missing
    return url if url.startswith("http") else "http://" + url
