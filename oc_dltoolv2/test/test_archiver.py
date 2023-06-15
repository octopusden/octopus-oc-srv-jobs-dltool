from io import BytesIO
from . import django_settings

from oc_delivery_apps.checksums.models import LocTypes, CiRegExp, CiTypes
from django import test
from fs.memoryfs import MemoryFS
from fs.zipfs import ZipFS

from oc_dltoolv2.archiver import DeliveryArchiver, ArchivationError
from oc_dltoolv2.resources import ResourceData, DeliveryResource, LocationStub

from oc_dltoolv2.test.mocks import mocked_requests
import mock
import os
import django


class TestResourceData(ResourceData):

    def get_content(self):
        return BytesIO("clean".encode("utf8"))


_branch_url = u"svn://repo/client/branch/"
_environ = {
    'CLIENT_PROVIDER_URL': 'http://test-client-provider',
    'DELIVERY_ADD_ARTS_PATH': 
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'delivery-add-arts-settings')}

_get_svn_resource = lambda path: _get_test_resource("SVN", _branch_url + path, "rev")
_get_nexus_resource = lambda gav: _get_test_resource("NXS", gav, None, citype='FILE')
_get_nexus_resource_rn = lambda gav: _get_test_resource('NXS', gav, None, citype='RELEASENOTES')


def _get_test_resource(loc_type_code, path, rev, citype=None):
    citype_found = None
    if citype:
        citype_found = CiTypes.objects.get(code=citype)
    location = LocationStub(LocTypes.objects.get(code=loc_type_code), citype_found, path, rev)
    return DeliveryResource(location, TestResourceData())


@mock.patch.dict('os.environ', _environ)
class ArchivationTestSuite(django.test.TransactionTestCase):

    def setUp(self):
        django.core.management.call_command('migrate', verbosity=0, interactive=False)
        LocTypes(code="SVN", name="SVN").save()
        LocTypes(code="NXS", name="NXS").save()
        work_fs = MemoryFS()
        CiTypes(code="RELEASENOTES", name="RELEASENOTES").save()
        CiTypes(code="FILE", name="FILE").save()
        delivery_params = self._delivery_params()
        self._archiver = DeliveryArchiver(work_fs, delivery_params)

    def tearDown(self):
        super().tearDownClass()
        django.core.management.call_command('flush', verbosity=0, interactive=False)

    def _delivery_params(self):
        return { u"mf_delivery_comment": u"test comment",
                u"mf_delivery_author": u"test_author",
                u"mf_ci_build": u"0",
                u"creation_date": u"1900-01-01 00:00:00.000000+00:00",
                u"mf_ci_job": u"queue",
                u"version": u"v19000101_1",
                u"mf_source_svn": _branch_url,
                u"mf_delivery_revision": 0,
                u"mf_delivery_files_specified": [],
                u"mf_tag_svn": _branch_url,
                u"groupid": u"test.delivery.group.id",
                u"artifactid": u"test_artifact_id"}

    def test_resources_required(self):
        with self.assertRaises(ArchivationError):
            self._archiver.build_archive([], _branch_url)

    def test_conflicting_names_failure(self):
        with self.assertRaises(ArchivationError):
            self._archiver.build_archive([_get_svn_resource("a.txt"), _get_svn_resource("a.txt")],
                                         _branch_url)

    def test_svn_url_prefix_match_expected(self):
        with self.assertRaises(ArchivationError):
            self._archiver.build_archive([_get_svn_resource("a.txt"),
                                          _get_svn_resource("b/c.txt")],
                                         "svn://repo/client/mismatch/")

    @mock.patch('requests.get', side_effect=mocked_requests)
    def test_svn_files_placed(self, mocked_requests):
        self.assert_archived([_get_svn_resource("a.txt"), _get_svn_resource("b/c.txt")],
                             [("/", ["a.txt", "b", "delivery_info.json"]), ("b", ["c.txt"])])

    @mock.patch('requests.get', side_effect=mocked_requests)
    def test_artifacts_placed(self, mocked_requests):
        self.assert_archived([_get_nexus_resource("g:a:v:zip"), _get_nexus_resource("g1:a1:v1")],
                             [("/", ["a-v.zip", "a1-v1.jar", "delivery_info.json"])])

    @mock.patch('requests.get', side_effect=mocked_requests)
    def test_releasenotes_placed(self, mocked_requests):
        self.assert_archived([_get_nexus_resource("g:a:v:zip"),
                              _get_nexus_resource_rn("RELEASENOTES:a:v:txt")],
                             [("/", ["a-v.zip", "Release Notes", "delivery_info.json"]),
                              ("Release Notes", ["Release notes a-v.txt"])])

    @mock.patch('requests.get', side_effect=mocked_requests)
    def test_both_sources_placed(self, mocked_requests):
        self.assert_archived([_get_svn_resource("a.txt"), _get_svn_resource("b/c.txt"),
                              _get_nexus_resource("g:a:v:zip"), _get_nexus_resource("g1:a1:v1")],
                             [("/", ["a.txt", "a-v.zip", "a1-v1.jar", "b", "delivery_info.json"]), ("b", ["c.txt"])])

    @mock.patch('requests.get', side_effect=mocked_requests)
    def test_similar_artifacts_files_separated(self, mocked_requests):
        self.assert_archived([_get_nexus_resource("g1:a:v:zip"), _get_nexus_resource("g2:a:v:zip"),
                              _get_nexus_resource("g3:foo:bar:zip"), ],
                             [("/", ["foo-bar.zip", "g1", "g2", "delivery_info.json"]), ("g1", ["a-v.zip"]),
                              ("g2", ["a-v.zip"])])

    @mock.patch('requests.get', side_effect=mocked_requests)
    def test_sql_installer_version_removed(self, mocked_requests):
        self.assert_archived([_get_nexus_resource("com.ow:load_sql:v123:ssp"), ],
                                 [("/", ["load_sql.ssp", "delivery_info.json"])])

    def test_missing_rule_failure(self):
        LocTypes(code="TEST", name="TEST").save()
        with self.assertRaises(ArchivationError):
            self._archiver.build_archive([_get_test_resource("TEST", "foo", "bar")], _branch_url)

    # actually there is no retrieval of database LocTypes
    # only code of resources's loc_type is performed
    # def test_db_setup_required(self)

    def assert_archived(self, resources, layout):
        archive_path = self._archiver.build_archive(resources, _branch_url)
        self.assert_archive_contains(archive_path, self._archiver, *layout)

    def assert_archive_contains(self, archive_path, archiver, *path_contents):
        """ Checks that zip with specified name exists in given fs 
        and specifies folders have given content"""
        self.assertTrue(archiver._work_fs.exists(archive_path))
        with archiver._work_fs.open(archive_path, mode="rb") as zip_file:
            with ZipFS(zip_file) as zip_fs:
                for dir_path, content in path_contents:
                    self.assertCountEqual(content, zip_fs.listdir(dir_path))

    @mock.patch.dict('os.environ', {'COUNTERPARTY_ENABLED': 'True'})
    @mock.patch('requests.get', side_effect=mocked_requests)
    def test_copyright_appended(self, mocked_reqeusts):
        # parse special customer for this case
        _delivery_params = self._delivery_params()
        _delivery_params[u'groupid'] = u'test.delivery.grup.id._TEST_ORG_CLIENT'
        self._archiver = DeliveryArchiver(MemoryFS(), _delivery_params)
        self.assert_archived([_get_nexus_resource("com.ow:load_sql:v123:ssp"), ],
                             [("/", ["load_sql.ssp", "delivery_info.json", "Copyright"])])
