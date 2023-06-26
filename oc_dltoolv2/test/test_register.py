from . import django_settings

from io import BytesIO

from oc_cdtapi import NexusAPI
from oc_delivery_apps.checksums.models import CiTypes, CsTypes, LocTypes, CiRegExp
from oc_checksumsq.checksums_interface import FileLocation
from django import test
from fs.memoryfs import MemoryFS
from fs.zipfs import ZipFS

from ..register import register_delivery_content, register_delivery_resource, RegisterError
from ..resources import DeliveryResource, LocationStub, ResourceData

import django


class TestResourceData(ResourceData):

    def get_content(self):
        return BytesIO("content".encode("utf8"))


class RegisterTestCase(test.TransactionTestCase):

    def setUp(self):
        django.core.management.call_command('migrate', verbosity=0, interactive=False)
        CsTypes(code="MD5").save()
        CiTypes.objects.get_or_create(code="DELIVERY", name="Client delivery",
                                      is_standard="N", is_deliverable=True)
        LocTypes.objects.get_or_create(code="NXS", name="Nexus")

    def tearDown(self):
        django.core.management.call_command('flush', verbosity=0, interactive=False)


class ContentRegistrationTestSuite(RegisterTestCase):

    def _get_archive_fs(self):
        mock_fs = MemoryFS()
        with mock_fs.openbin(u"foo.zip", "w") as zip_file:
            with ZipFS(zip_file, write=True) as new_zip:
                new_zip.writetext(u"a", u"a")
                new_zip.makedirs(u"b")
                new_zip.writetext(u"b/c", u"c")
        return mock_fs

    class MockRegistrationClient(object):

        def register_file(self, file_location, citype_code, depth):
            if not hasattr(self, "calls"):
                self.calls = []
            self.calls.append((file_location, citype_code, depth))

    def test_empty_file_rejected(self):
        mock_fs = MemoryFS()
        mock_fs.create(u"foo.zip")
        with self.assertRaisesRegex(RegisterError, "empty"):
            register_delivery_content(mock_fs, "foo.zip", NexusAPI.parse_gav("g:a:v"),
                                      ContentRegistrationTestSuite.MockRegistrationClient())

    def test_missing_delivery_rejected(self):
        mock_fs = MemoryFS()
        with self.assertRaisesRegexp(RegisterError, "not found"):
            register_delivery_content(mock_fs, "foo.zip", NexusAPI.parse_gav("g:a:v"),
                                      ContentRegistrationTestSuite.MockRegistrationClient())

    def test_archive_registered(self):
        mock_fs = self._get_archive_fs()
        registration_client = ContentRegistrationTestSuite.MockRegistrationClient()
        register_delivery_content(mock_fs, "foo.zip", NexusAPI.parse_gav("g:a:v"),
                                  registration_client)

        expected_params = [(("g:a:v:zip", "NXS", None), "DELIVERY", 1), ]
        self.assertCountEqual(expected_params, registration_client.calls)


class SourceRegisterTestSuite(RegisterTestCase):

    class MockRegistrationClient(object):

        def register_checksum(self, location, checksum, citype=None):
            if not hasattr(self, "calls"):
                self.calls = []
            self.calls.append((location, checksum, citype))

    def setUp(self):
        super(SourceRegisterTestSuite, self).setUp()

        svn_file = CiTypes(code="FOO", name="bar", is_standard="N", is_deliverable=True)
        svn_file.save()
        LocTypes(code="SVN", name="SVN").save()

        CiRegExp(loc_type=LocTypes.objects.get(code="SVN"),
                 ci_type=svn_file, regexp=".+").save()

    def test_resource_registered(self):
        location = LocationStub(LocTypes.objects.get(code="SVN"), CiTypes.objects.get(code="FOO"),
                                "https://svn/path", "rev")
        resource = DeliveryResource(location, TestResourceData())

        registration_client = SourceRegisterTestSuite.MockRegistrationClient()
        register_delivery_resource(resource, registration_client, None)

        file_location = FileLocation(location.path, location.location_type.code, location.revision)
        expected_params = [(file_location, "9a0364b9e99bb480dd25e1f0284c8555", "FOO"), ]
        self.assertCountEqual(expected_params, registration_client.calls)
    
    def test_resource_registered_with_prepared_checksums_list(self):
        location = LocationStub(LocTypes.objects.get(code="SVN"), CiTypes.objects.get(code="FOO"),
                                "https://svn/path", "rev")
        resource = DeliveryResource(location, TestResourceData())

        registration_client = SourceRegisterTestSuite.MockRegistrationClient()
        register_delivery_resource(resource, registration_client, [{"path": location.path, "checksum": "9a0364b9e99bb480dd25e1f0284c8555"}])

        file_location = FileLocation(location.path, location.location_type.code, location.revision)
        expected_params = [(file_location, "9a0364b9e99bb480dd25e1f0284c8555", "FOO"), ]
        self.assertCountEqual(expected_params, registration_client.calls)

