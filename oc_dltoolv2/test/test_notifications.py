import unittest
from collections import namedtuple

from oc_cdtapi import NexusAPI

from ..notifications import Notificator

MockMailEntry = namedtuple("MockMailEntry", ("recipient", "subject", "text"))


class NotificatorTestSuite(unittest.TestCase):

    def get_mailer(self):
        class MockMailer(object):
            def __init__(self):
                self.sent_entries = []

            def send_email(self, to_addresses, subject, text):
                self.sent_entries.append(MockMailEntry(to_addresses, subject, text))

        return MockMailer()

    def get_notificator(self, mailer):
        return Notificator(mailer, "portal.com", "ci.com")

    def test_success_send(self):
        mailer = self.get_mailer()
        notificator = self.get_notificator(mailer)
        gav = NexusAPI.parse_gav("g:a:v")
        notificator.send_success_notification("a@ow.com", gav)
        self.assertEqual(1, len(mailer.sent_entries))
        entry = mailer.sent_entries[0]
        self.assertEqual(["a@ow.com", ], entry.recipient)
        self.assertIn("successfully", entry.subject)
        self.assertIn("g:a:v", entry.text)
        self.assertIn("g/a/v", entry.text)  # part of portal link

    def test_failure_send(self):
        mailer = self.get_mailer()
        notificator = self.get_notificator(mailer)
        gav = NexusAPI.parse_gav("g:a:v")
        notificator.send_failure_notification("a@ow.com", gav, None, None)
        self.assertEqual(1, len(mailer.sent_entries))
        entry = mailer.sent_entries[0]
        self.assertEqual(["a@ow.com", ], entry.recipient)
        self.assertIn("failed", entry.subject)
        self.assertIn("g:a:v", entry.text)
