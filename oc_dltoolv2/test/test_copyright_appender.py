from . import django_settings
from django import test
import django
import fs
import os
import mock
from oc_dltoolv2.delivery_copyright_appender import DeliveryCopyrightAppender
from oc_dltoolv2.test.mocks import mocked_requests

_environ = {
    'CLIENT_PROVIDER_URL': 'http://test-client-provider',
    'DELIVERY_ADD_ARTS_PATH': 
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'delivery-add-arts-settings')}

@mock.patch.dict('os.environ', _environ)
class DeliveryCopyrightAppenderTest(django.test.TransactionTestCase):

    def setUp(self):
        django.core.management.call_command('migrate', verbosity=0, interactive=False)

    def tearDown(self):
        django.core.management.call_command('flush', verbosity=0, interactive=False)
    
    @mock.patch('requests.get', side_effect=mocked_requests)
    def test_append__com(self, mocked_requests):
        _prms={'groupid': 'test.delivery.group.id._TEST_COM_CLIENT'}
        with fs.tempfs.TempFS() as _wfs:
            DeliveryCopyrightAppender(_prms).write_to_file(_wfs, "Copyright")
            # should be just a copy of com-licensed file
            with fs.osfs.OSFS(os.getenv('DELIVERY_ADD_ARTS_PATH')) as _osfs:
                with _osfs.open("copyright-com.txt", mode="r") as _original:
                    with _wfs.open("Copyright", mode="r") as _copy:
                        self.assertEqual(_original.read().strip(), _copy.read().strip())

    @mock.patch('requests.get', side_effect=mocked_requests)
    def test_append__org(self, mocked_requests):
        _prms={'groupid': 'test.delivery.group.id._TEST_ORG_CLIENT'}
        with fs.tempfs.TempFS() as _wfs:
            DeliveryCopyrightAppender(_prms).write_to_file(_wfs, "Copyright")
            # should be just a copy of com-licensed file
            with fs.osfs.OSFS(os.getenv('DELIVERY_ADD_ARTS_PATH')) as _osfs:
                with _osfs.open("copyright-org.txt", mode="r") as _original:
                    with _wfs.open("Copyright", mode="r") as _copy:
                        self.assertEqual(_original.read().strip(), _copy.read().strip())

    @mock.patch('requests.get', side_effect=mocked_requests)
    def test_append__nothing(self, mocked_requests):
        _prms={'groupid': 'test.delivery.group.id._TEST_CLIENT'}
        with fs.tempfs.TempFS() as _wfs:
            DeliveryCopyrightAppender(_prms).write_to_file(_wfs, "Copyright")
            self.assertFalse(_wfs.exists("Copyright"))
