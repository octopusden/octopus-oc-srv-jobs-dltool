from unittest import mock
import django
from django import test
from . import django_settings
from oc_dltoolv2.delivery_artifacts_checker import DeliveryArtifactsChecker
from oc_dltoolv2.delivery_exceptions import DeliveryDeniedException
from oc_dltoolv2.resources import ResourceData, DeliveryResource, LocationStub
from oc_dltoolv2.test.mocks import mocked_requests
from tempfile import NamedTemporaryFile
from oc_delivery_apps.checksums.models import LocTypes, CiTypes

import os

class TestResourceData(ResourceData):
    def get_content(self):
        return BytesIO("clean".encode("utf8"))

_environ = {
    'CLIENT_PROVIDER_URL': 'http://test-client-provider',
    'DELIVERY_ADD_ARTS_PATH': 
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'delivery-add-arts-settings')}

@mock.patch.dict('os.environ', _environ)
class DeliveryArtifactsCheckerTest(django.test.TransactionTestCase):
    def setUp(self):
        django.core.management.call_command('migrate', verbosity=0, interactive=False)
        self.maxDiff = None
        # creating CiTypes necessary
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
            DeliveryArtifactsChecker(None)

    def test_get_artifacts_lineup__org(self):
        self.assertEqual(DeliveryArtifactsChecker({"any":"any"})._get_artifacts_lineup("org"),
                (None, 
                    ["^com\\.example\\.ext\\.documentation:[^:]+-(english|russian):[^:]+:[^:]+(:[^:]+)*$"]))

    def test_get_artifacts_lineup__com(self):
        self.assertEqual(DeliveryArtifactsChecker({"any":"any"})._get_artifacts_lineup("com"),
                (None, 
                    ["^com\\.example\\.ext\\.documentation:[^:]+-(en|ru):[^:]+:[^:]+(:[^:]+)*$"]))

    def test_get_artifacts_lineup__any(self):
        with self.assertRaises(AttributeError):
            DeliveryArtifactsChecker({"any":"any"})._get_artifacts_lineup("any")

    def test_get_artifacts_lineup__none(self):
        with self.assertRaises(AttributeError):
            DeliveryArtifactsChecker({"any":"any"})._get_artifacts_lineup(None)

    def test_check_artifacts_lineup__ok(self):
        _resources=[self._get_test_resource("test.doc.group.id:anydoc-russian:v1:zip"),
                self._get_test_resource("test.doc.group.id:anydoc-english:v2:zip")]
        _list_necessary = ["^test\.doc\.group\.id:anydoc-english:[^:]+:[^:]+(:[^:]+)*$"]
        _list_denied = ["^test\.doc\.group\.id:anydoc-eng:[^:]+:[^:]+(:[^:]+)*$"]
        self.assertTrue(DeliveryArtifactsChecker({"any":"any"}).
                _check_artifacts_lineup(_resources, _list_necessary, _list_denied))

    def test_check_artifacts_lieup__fail_necessary(self):
        _resources=[self._get_test_resource("test.doc.group.id:anydoc-russian:v1:zip"),
                self._get_test_resource("test.doc.group.id:anydoc-english:v2:zip")]
        _list_necessary = ["^test\.doc\.group\.id:anydoc-eng:[^:]+:[^:]+(:[^:]+)*$"]
        _list_denied = ["^test\.doc\.group\.id:anydoc-rus:[^:]+:[^:]+(:[^:]+)*$"]
        with self.assertRaises(DeliveryDeniedException):
            DeliveryArtifactsChecker({"any":"any"})._check_artifacts_lineup(_resources, 
                    _list_necessary, _list_denied)

    def test_check_artifacts_lieup__fail_denied(self):
        _resources=[self._get_test_resource("test.doc.group.id:anydoc-russian:v1:zip"),
                self._get_test_resource("test.doc.group.id:anydoc-english:v2:zip")]
        _list_necessary = ["^test\.doc\.group\.id:anydoc-russian:[^:]+:[^:]+(:[^:]+)*$"]
        _list_denied = ["^test\.doc\.group\.id:anydoc-english:[^:]+:[^:]+(:[^:]+)*$"]
        with self.assertRaises(DeliveryDeniedException):
            DeliveryArtifactsChecker({"any":"any"})._check_artifacts_lineup(_resources, 
                    _list_necessary, _list_denied)

    def test_check_resources_lineup__ok(self):
        _resources=[self._get_test_resource("test.doc.group.id:anydoc-russian:v1:zip"),
                self._get_test_resource("test.doc.group.id:anydoc-english:v2:zip")]
        _list = ["^test\.doc\.group\.id:anydoc-english:[^:]+:[^:]+(:[^:]+)*$"]
        self.assertIsNone(DeliveryArtifactsChecker({"any":"any"})._check_resources_lineup(_resources, _list, True))
        _list = ["^test\.doc\.group\.id:anydoc-eng:[^:]+:[^:]+(:[^:]+)*$"]
        self.assertIsNone(DeliveryArtifactsChecker({"any":"any"})._check_resources_lineup(_resources, _list, False))

    def test_check_resources_lineup__fail(self):
        _resources=[self._get_test_resource("test.doc.group.id:anydoc-russian:v1:zip"),
                self._get_test_resource("test.doc.group.id:anydoc-english:v2:zip")]
        _list = ["^test\.doc\.group\.id:anydoc-eng:[^:]+:[^:]+(:[^:]+)*$"]
        with self.assertRaises(DeliveryDeniedException):
            DeliveryArtifactsChecker({"any":"any"})._check_resources_lineup(_resources, _list, True)
        _list = ["^test\.doc\.group\.id:anydoc-english:[^:]+:[^:]+(:[^:]+)*$"]
        with self.assertRaises(DeliveryDeniedException):
            DeliveryArtifactsChecker({"any":"any"})._check_resources_lineup(_resources, _list, False)

    #check_artifacts_included, _check_artifacts_lineup, _check_resources_lineup are tested all tougether
    @mock.patch('requests.get', side_effect=mocked_requests)
    def test_check_artifacts_included__all_ok(self, mocked_requests):
        _resources=[self._get_test_resource("com.example.ext.documentation:anydoc-russian:v1:zip"),
                self._get_test_resource("com.example.ext.documentation:anydoc-english:v2:zip")]
        _prms={"groupid": "test.delivery.group.id._TEST_COM_CLIENT"}
        self.assertTrue(DeliveryArtifactsChecker(_prms).check_artifacts_included(_resources))

    @mock.patch('requests.get', side_effect=mocked_requests)
    def test_check_artifacts_included__denied_present(self, mocked_requests):
        _resources=[self._get_test_resource("com.example.ext.documentation:anydoc-russian:v1:zip"),
                self._get_test_resource("com.example.ext.documentation:anydoc-english:v2:zip")]
        _prms={"groupid": "test.delivery.group.id._TEST_ORG_CLIENT"}
        with self.assertRaises(DeliveryDeniedException):
            DeliveryArtifactsChecker(_prms).check_artifacts_included(_resources)

    @mock.patch('requests.get', side_effect=mocked_requests)
    def test_check_artifacts_included__no_counterparty(self, mocked_requests):
        _resources=[self._get_test_resource("com.example.ext.documentation:anydoc-russian:v1:zip"),
                self._get_test_resource("com.example.ext.documentation:anydoc-english:v2:zip")]
        _prms={"groupid": "test.delivery.group.id._TEST_CLIENT"}
        self.assertTrue(DeliveryArtifactsChecker(_prms).check_artifacts_included(_resources))

