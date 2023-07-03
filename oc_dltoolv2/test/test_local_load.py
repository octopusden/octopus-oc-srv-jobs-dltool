from . import django_settings

from io import BytesIO

from oc_delivery_apps.checksums.models import LocTypes
from django import test
import django
from fs.errors import ResourceNotFound
from fs.memoryfs import MemoryFS

from ..local_load import download_resource
from ..resources import ResourceData, DeliveryResource, LocationStub


class TestResourceData(ResourceData):

    def __init__(self, content):
        self._content = content

    def get_content(self):
        return BytesIO(self._content.encode("utf8"))


class LocalLoadTestSuite(test.TransactionTestCase):

    def setUp(self):
        django.core.management.call_command('migrate', verbosity=0, interactive=False)
        test_loc_type = LocTypes(code="TEST", name="TEST")
        test_loc_type.save()
        self.test_location = LocationStub(test_loc_type, None, "unused", "rev")

    def tearDown(self):
        django.core.management.call_command('flush', verbosity=0, interactive=False)

    def create_resource(self, path):
        resource_data = TestResourceData(path)
        return DeliveryResource(self.test_location, resource_data)

    def test_resource_loaded(self):
        work_fs = MemoryFS()
        loaded_resource = download_resource(self.create_resource("a.txt"), work_fs)
        self.assertEqual(self.test_location, loaded_resource.location_stub)
        with loaded_resource.resource_data.get_content() as content_handle:
            self.assertEqual("a.txt", content_handle.read().decode("utf8"))
        walk_result = list(work_fs.walk.files())
        self.assertEqual(1, len(walk_result))
        self.assertEqual("a.txt", work_fs.readtext(walk_result[0]))

    def test_local_cache_required(self):
        work_fs = MemoryFS()
        loaded_resource = download_resource(self.create_resource("a.txt"), work_fs)
        filenames = list(work_fs.walk.files())  # evaluate iterator before removing files
        for filename in filenames:
            work_fs.remove(filename)
        with self.assertRaises(ResourceNotFound):
            loaded_resource.resource_data.get_content()
