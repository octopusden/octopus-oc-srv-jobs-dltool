from django import test
import django
from . import django_settings
from unittest import mock
from ..delivery_info_helper import DeliveryInfoHelper
from ..delivery_exceptions import DeliveryDeniedException
from ..resources import ResourceData, DeliveryResource, LocationStub
from .mocks import mocked_requests
import os
from tempfile import NamedTemporaryFile
from oc_delivery_apps.checksums.models import LocTypes, CiTypes

class TestResourceData(ResourceData):
    def get_content(self):
        return BytesIO("clean".encode("utf8"))

_environ = {
    'CLIENT_PROVIDER_URL': 'http://test-client-provider',
    'DELIVERY_ADD_ARTS_PATH': 
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'delivery-add-arts-settings')}

@mock.patch.dict('os.environ', _environ)
class DeliveryInfoHelperTest(django.test.TransactionTestCase):
    def setUp(self):
        self.maxDiff = None
        django.core.management.call_command('migrate', verbosity=0, interactive=False)
        # creating required CiTypes 
        LocTypes.objects.get_or_create(code="NXS", name="NXS")[0].save()
        CiTypes.objects.get_or_create(code="TSTDSTR", name="TSTDSTR")[0].save()

    def tearDown(self):
        django.core.management.call_command('flush', verbosity=0, interactive=False)

    def _get_test_resource(self, gav):
        citype_found = CiTypes.objects.get(code="TSTDSTR")
        location = LocationStub(LocTypes.objects.get(code="NXS"), citype_found, gav, None)
        return DeliveryResource(location, TestResourceData())

    def test_init(self):
        with self.assertRaises(ValueError):
            DeliveryInfoHelper(None)

    def test_find_customer_code__gav(self):
        _prms={"groupid": "test.delivery.group.id.TEST_CLIENT"}
        self.assertEqual(DeliveryInfoHelper(_prms)._find_customer_code(), "TEST_CLIENT")

    def test_find_customer_code__svn_branch(self):
        _prms={"mf_source_svn": "svn://test.svn.server.local/svn/repo/country/TEST_CLIENT/branches/branch"}
        self.assertEqual(DeliveryInfoHelper(_prms)._find_customer_code(), "TEST_CLIENT")
        _prms={"mf_source_svn": "svn://test.svn.server.local/svn/repo/country/TEST_CLIENT/trunk"}
        self.assertEqual(DeliveryInfoHelper(_prms)._find_customer_code(), "TEST_CLIENT")

    def test_find_customer_code__svn_tag(self):
        _prms={"mf_tag_svn": "svn://test.svn.server.local/svn/repo/country/TEST_CLIENT/tags/tag"}
        self.assertEqual(DeliveryInfoHelper(_prms)._find_customer_code(), "TEST_CLIENT")

    def test_find_customer_code__fail(self):
        self.assertIsNone(DeliveryInfoHelper({"any_parameter": "any_value"})._find_customer_code())

    # for these tests see included configuration files placed in 'DELIVERY_ADD_ARTS_PATH'
    # in "mock" above
    @mock.patch('requests.get', side_effect=mocked_requests)
    def test_get_customer_location__org(self, mocked_requests):
        self.assertEqual(
                DeliveryInfoHelper({"any_parameter": "any_value"})._get_customer_location("_TEST_ORG_CLIENT"),
                "org")

    @mock.patch('requests.get', side_effect=mocked_requests)
    def test_get_customer_location__com(self, moceked_requests):
        self.assertEqual(
                DeliveryInfoHelper({"any_parameter": "any_value"})._get_customer_location("_TEST_COM_CLIENT"),
                "com")

    @mock.patch('requests.get', side_effect=mocked_requests)
    def test_get_customer_location__none(self, mocked_requests):
        self.assertIsNone(
                DeliveryInfoHelper({"any_parameter": "any_value"})._get_customer_location("_TEST_CLIENT"))

    def test_read_artifacts_conf__com(self):
        self.assertCountEqual(DeliveryInfoHelper({"any":"any"})._read_artifacts_conf("com"),
                {"denied":[
                    "^com\\.example\\.ext\\.documentation:[^:]+-(en|ru):[^:]+:[^:]+(:[^:]+)*$"],
                    "copyright": "copyright-com.txt"})

    def test_read_artifacts_conf__org(self):
        self.assertCountEqual(DeliveryInfoHelper({"any":"any"})._read_artifacts_conf("org"),
                {"denied":[
                    "^com\\.example\\.ext\\.documentation:[^:]+-(english|russian):[^:]+:[^:]+(:[^:]+)*$"],
                    "copyright": "copyright-org.txt"})

    @mock.patch.dict('os.environ', {'DELIVERY_ADD_ARTS_PATH':""})
    def test_read_artifacts_conf__no_var(self):
        with self.assertRaises(ValueError):
            DeliveryInfoHelper({"any":"any"})._read_artifacts_conf("org")

    @mock.patch.dict('os.environ', {'DELIVERY_ADD_ARTS_PATH': 
        os.path.join(os.path.dirname(NamedTemporaryFile().name), 'nonexistent-artifacts-settings')})
    def test_read_artifacts_conf__no_file(self):
        with self.assertRaises(IOError):
            DeliveryInfoHelper({"any":"any"})._read_artifacts_conf("org")

    def test_read_artifacts_conf__no_location(self):
        self.assertIsNone(DeliveryInfoHelper({"any":"any"})._read_artifacts_conf("any"))

