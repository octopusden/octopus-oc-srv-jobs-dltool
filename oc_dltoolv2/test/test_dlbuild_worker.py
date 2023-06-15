from . import django_settings
from oc_cdt_queue2.test.synchron.mocks.queue_loopback import LoopbackConnection
from django.test import TransactionTestCase
import django

from oc_dlinterface.dlbuild_worker_interface import DLBuildQueueClient
from oc_dltoolv2.test.mocks import MockConnectionManager, DLBuildWorkerMock


class DLBuildWorkerTest(TransactionTestCase):
    def setUp(self):
        django.core.management.call_command('migrate', verbosity=0, interactive=False)
        self.app = DLBuildWorkerMock(setup_orm=False, conn_mgr=MockConnectionManager())
        self.rpc = DLBuildQueueClient()

        self.rpc._Connection = LoopbackConnection
        self.app._Connection = LoopbackConnection

        self.rpc.setup("amqp://127.0.0.1/", queue="cdt_dltest_input")
        self.rpc.connect()

    def tearDown(self):
        django.core.management.call_command('flush', verbosity=0, interactive=False)

    def test_ping(self):
        self.assertIsNone(self.app.ping())
