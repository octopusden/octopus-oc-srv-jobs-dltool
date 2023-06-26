from django import test
from . import django_settings
from ..delivery_info_decoder import DeliveryInfoDecoder
from fs.tempfs import TempFS
import json
import random
import string
import django
from oc_delivery_apps.checksums.models import LocTypes, CiTypes
from ..resources import ResourceData, DeliveryResource, LocationStub
from io import BytesIO
from copy import deepcopy
import os
from unittest import mock

_environ = {
    'CLIENT_PROVIDER_URL': 'http://test-client-provider',
    'DELIVERY_ADD_ARTS_PATH': 
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'delivery-add-arts-settings')}

class TestResourceData(ResourceData):
    def get_content(self):
        return BytesIO("clean".encode("utf8"))

@mock.patch.dict('os.environ', _environ)
class DeliveryInfoDecoderTest(django.test.TransactionTestCase):

    def setUp(self):
        self.maxDiff = None
        django.core.management.call_command('migrate', verbosity=0, interactive=False)
        # creating required CiTypes 
        LocTypes.objects.get_or_create(code="SVN", name="SVN")[0].save()
        LocTypes.objects.get_or_create(code="NXS", name="NXS")[0].save()
        CiTypes.objects.get_or_create(code="RELEASENOTES", name="RELEASENOTES")[0].save()
        CiTypes.objects.get_or_create(code="FILE", name="FILE")[0].save()
        CiTypes.objects.get_or_create(code="SVNFILE", name="SVNFILE")[0].save()
        CiTypes.objects.get_or_create(code="TSTDSTR", name="TSTDSTR")[0].save()
        CiTypes.objects.get_or_create(code="TSTDSTRCLIENT", name="TSTDSTRCLIENT")[0].save()

    def tearDown(self):
        django.core.management.call_command('flush', verbosity=0, interactive=False)
    @property
    def _random_filename(self):
        return ''.join(random.choice(string.ascii_lowercase) for i in range(8))

    def _get_test_resource(self, loc_type_code, path, rev, citype=None):
        citype_found = None
        if citype:
            citype_found = CiTypes.objects.get(code=citype)
        location = LocationStub(LocTypes.objects.get(code=loc_type_code), citype_found, path, rev)
        return (DeliveryResource(location, TestResourceData()), self._random_filename)

    def _assertListItemsEqual(self, list_1, list_2):
        self.assertCountEqual(list_1, list_2)

        while len(list_1) and len(list_2):
            _d1 = list_1.pop()
            assert(_d1 in list_2)
            _d2 = list_2.pop(list_2.index(_d1))
            if isinstance(_d1, dict):
                self._assertDictItemsEqual(_d1, _d2)
                continue
            if isinstance(_d1, list):
                self._assertListItemsEqual(_d1, _d2)
                continue

            self.assertEqual(_d1, _d2)

    def _assertDictItemsEqual(self, dict_1, dict_2):
        # we are in python 2.7 and there is no 'assertDictEqual' yet
        # write it ourselves.
        self.assertCountEqual(dict_1, dict_2)
        for _t in dict_1.keys():
            _d1 = dict_1.get(_t)
            _d2 = dict_2.get(_t)
            self.assertEqual(type(_d1), type(_d2))
            if isinstance(_d1, dict):
                self._assertDictItemsEqual(_d1, _d2)
                continue
            if isinstance(_d1, list):
                self._assertListItemsEqual(_d1, _d2)
                continue

            self.assertEqual(_d1, _d2)

    def _assert_results(self, delivery_params, delivery_resources, expected_result):
        with TempFS() as _work_fs:
            _filename = self._random_filename
            DeliveryInfoDecoder(delivery_params, delivery_resources).write_to_file(_work_fs, _filename)
            with _work_fs.open(_filename) as _fl_in:
                _json_data = json.loads(_fl_in.read())
                self._assertDictItemsEqual(_json_data, expected_result)

    def _resources_to_files(self, _delivery_resources):
        _result = list()
        for _res in _delivery_resources:
            _result.append(
                    {u"path": _res[1], u"citype": _res[0].location_stub.citype.code})
        return _result

    def test_all_ok(self):
        _delivery_params = {
                u"mf_delivery_files_specified":
                        '\n'.join([
                        "test.group.id:test_artifact_id:1:pkg",
                        "test.group.id:test_artifact_id:2:pkg",
                        "svn://test-svn/svn/subrepo/country/_TEST_CLIENT/branches/branch/file.ext"]),
                u"version": u"v1_1",
                u"mf_source_svn": u"svn://test-svn/svn/subrepo/country/_TEST_CLIENT/branches/branch",
                u"mf_delivery_comment": u"Test Delivery Comment, с кириллицей",
                u"mf_delivery_author": u"test_author",
                u"creation_date": u"1900-01-01 00:00:00.000000+00:00",
                u"mf_tag_svn": u"svn://test-svn/svn/subrepo/country/_TEST_CLIENT/tags/prj-_TEST_CLIENT-tag",
                u"groupid": u"test.delivery.group.id._TEST_CLIENT",
                u"artifactid": u"test_delivery_TEST_CLIENT-tag" }
        _delivery_resources = [
                self._get_test_resource("NXS", "test.group.id:test_artifact_id:1:pkg", None, "TSTDSTR"),
                self._get_test_resource("NXS", "test.group.id:test_artifact_id:2:pkg", None, "TSTDSTRCLIENT"),
                self._get_test_resource(
                    "SVN", 
                    "svn://test-svn/svn/subrepo/country/_TEST_CLIENT/branches/branch/file.ext",
                    "rev", "SVNFILE") ]
        _expected_result = {
            u'deliveryId': u"_TEST_CLIENT:test_delivery_TEST_CLIENT-tag:v1_1",
            u'deliveryFiles': self._resources_to_files(_delivery_resources)}

        self._assert_results(_delivery_params, _delivery_resources, _expected_result)

    def test_no_delivery_gav(self):
        # incorrect appending of delivery GAV should not stack the process
        _delivery_params = {
                u"mf_delivery_files_specified":
                        '\n'.join([
                        "test.group.id:test_artifact_id:1.1:pkg",
                        "test.group.id:test_artifact_id:2.1:pkg",
                        "svn://test-svn/svn/subrepo/country/_TEST_CLIENT/branches/branch/file.ext"]),
                u"version": u"v1_2",
                u"mf_source_svn": u"svn://test-svn/svn/subrepo/country/_TEST_CLIENT/branches/branch",
                u"mf_delivery_comment": u"Test Delivery Comment, с кириллицей",
                u"mf_delivery_author": u"test_author",
                u"creation_date": u"1900-01-01 00:00:00.000000+00:00",
                u"mf_tag_svn": u"svn://test-svn/svn/subrepo/country/_TEST_CLIENT/tags/prj-_TEST_CLIENT-tag",
                u"artifactid": u"test_delivery_TEST_CLIENT-tag" }
        _delivery_resources = [
                self._get_test_resource("NXS", "test.group.id:test_artifact_id:1.1:pkg", None, "TSTDSTR"),
                self._get_test_resource("NXS", "test.group.id:test_artifact_id:2.1:pkg", None, "TSTDSTRCLIENT"),
                self._get_test_resource(
                    "SVN", 
                    "svn://test-svn/svn/subrepo/country/_TEST_CLIENT/branches/branch/file.ext",
                    "rev", "SVNFILE") ]
        _expected_result = {
                u"deliveryId": u"_TEST_CLIENT:test_delivery_TEST_CLIENT-tag:v1_2",
                u"deliveryFiles": self._resources_to_files(_delivery_resources)}

        self._assert_results(_delivery_params, _delivery_resources, _expected_result)

    def test_no_resources(self):
        # all OK but "required_gavs" and "delivery_files" should be absent
        _delivery_params = {
                u"mf_delivery_files_specified":
                    '\n'.join([
                        "test.group.id:test_artifact_id:1:pkg",
                        "test.group.id:test_artifact_id:2:pkg",
                        "svn://test-svn/svn/subrepo/country/_TEST_CLIENT/branches/branch/file.ext"]),
                u"version": u"v1_1",
                u"mf_source_svn": u"svn://test-svn/svn/subrepo/country/_TEST_CLIENT/branches/branch",
                u"mf_delivery_comment": u"Test Delivery Comment, с кириллицей",
                u"mf_delivery_author": u"test_author",
                u"creation_date": u"1900-01-01 00:00:00.000000+00:00",
                u"mf_tag_svn": u"svn://test-svn/svn/subrepo/country/_TEST_CLIENT/tags/prj-_TEST_CLIENT-tag",
                u"groupid": u"test.delivery.group.id._TEST_CLIENT",
                u"artifactid": u"test_delivery_TEST_CLIENT-tag" }
        _delivery_resources = []
        _expected_result = {u"deliveryId": u"_TEST_CLIENT:test_delivery_TEST_CLIENT-tag:v1_1", u"deliveryFiles": []}
        self._assert_results(_delivery_params, _delivery_resources, _expected_result)

    def test_fail(self):
        # this case decoder should write nothing, so JSON decoder will raise 'ValueError'
        with self.assertRaises(ValueError):
            self._assert_results({}, [], {})
