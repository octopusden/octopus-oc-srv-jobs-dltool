from . import django_settings
import os
from oc_cdtapi import NexusAPI
from oc_delivery_apps.checksums.controllers import CheckSumsController
from oc_delivery_apps.checksums.models import LocTypes, CiTypeGroups, CiTypes, CiRegExp, CiTypeIncs, CsTypes
from django import test
import django
from oc_delivery_apps.dlmanager.DLModels import DeliveryList
from oc_delivery_apps.dlmanager.models import PrivateFile
from fs.errors import DirectoryExists
from fs.info import Info
from fs.memoryfs import MemoryFS

from ..resolver import BuildRequestResolver, ResolutionError
from ..resources import RequestContext

from unittest import mock

class TestFS(MemoryFS):

    def __init__(self, scheme):
        super(TestFS, self).__init__()
        self._scheme = scheme
        self._revision = "rev" if scheme == "svn" else None

    def getsyspath(self, path):
        return ((self._scheme + "://" + path) if self._scheme else path)

    def getinfo(self, path, namespaces=["basic"]):
        info = super(TestFS, self).getinfo(path, namespaces)
        if "svn" in namespaces:
            raw_info = info.raw
            raw_info["svn"] = {"revision": self._revision}
            info = Info(raw_info)
        return info


def get_request_context(svn_files=[], artifacts=[]):
    svn_fs = TestFS("svn")
    for path in svn_files:
        target_dir = os.path.dirname(path) if not path.endswith("/") else path
        try:
            svn_fs.makedirs(target_dir)
        except DirectoryExists:
            pass
        if not path.endswith("/"):
            svn_fs.writetext(path, path)
    nexus_fs = TestFS(None)
    for gav in artifacts:
        nexus_fs.writetext(gav, gav)
        with nexus_fs.openbin(gav) as artifact:
            parsed_gav = NexusAPI.parse_gav(gav)
            if 'release_notes' in parsed_gav.get('g'):
                CheckSumsController().register_file_obj(artifact, 'RELEASENOTES', gav, 'NXS')
            else:
                CheckSumsController().register_file_obj(artifact, "ARTIFACT", gav, "NXS")
    return RequestContext(svn_fs, nexus_fs)


def resolve(delivery_list, context):
    return BuildRequestResolver().resolve_request(delivery_list, context)


class RequestResolutionTestSuite(test.TransactionTestCase):

    def setUp(self):
        django.core.management.call_command('migrate', verbosity=0, interactive=False)
        LocTypes(code="SVN", name="SVN").save()
        at_nxs, _ = LocTypes.objects.get_or_create(code="NXS", name="NXS")

        CiTypes(code="SVNFILE", name="SVNFILE").save()
        artifacts_citype, _ = CiTypes.objects.get_or_create(code="ARTIFACT", name="ARTIFACT")
        CiRegExp(loc_type=at_nxs, ci_type=artifacts_citype, regexp=".+").save()

        CiTypes(code="RELEASENOTES", name="RELEASENOTES").save()
        CiTypes(code="FILE", name="FILE").save()
        CsTypes(code="MD5", name="MD5 digest algoritm").save()

    def tearDown(self):
        django.core.management.call_command('flush', verbosity=0, interactive=False)

    def assert_request_resolved(self, actual_resources, context,
                                clean_svn_files=[], artifacts=[]):
        expected_svn_urls = ["svn://" + path for path in clean_svn_files]
        expected_nexus_urls = artifacts
        actual_urls = [resource.location_stub.path for resource in actual_resources]
        self.assertCountEqual(expected_svn_urls + expected_nexus_urls, actual_urls)
        get_location_code = lambda resource: resource.location_stub.location_type.code
        filter_resources = lambda location_code: lambda resource: get_location_code(resource) == location_code
        svn_resources = list(filter(filter_resources("SVN"), actual_resources))
        for svn_path in clean_svn_files:
            self._assert_resource_matches(svn_path, svn_resources, context.svn_fs, ["SVNFILE"])
        nexus_resources = list(filter(filter_resources("NXS"), actual_resources))
        for gav in artifacts:
            self._assert_resource_matches(gav, nexus_resources, context.nexus_fs,
                                          ["ARTIFACT", "RELEASENOTES"])

    def _assert_resource_matches(self, path, resources, test_fs, allowed_citype_codes):
        #print ('RESOURCES: %s' % resources)
        # location type is tested in filter, path existence is checked in lists comparison
        url = test_fs.getsyspath(path)
        resource_list = list(filter(lambda rsc: rsc.location_stub.path == url, resources))
        #print ("RESOURCE LIST LENGTH: %s" % len(resource_list) )
        #print ("RESOURCE LIST TYPE: %s" % type(resource_list) )
        resource = None
        if resource_list:
            resource = resource_list[0]
        #print ("RESOURCE TYPE: %s" % type(resource) )
        #print ("RESOURCE : %s" % str(resource))
        location = resource.location_stub
        expected_content = test_fs.readtext(path)
        with resource.resource_data.get_content() as content_handle:
            actual_content = content_handle.read().decode("utf8")
        self.assertEqual(expected_content, actual_content)
        self.assertEqual(test_fs._revision, location.revision)
        self.assertIn(location.citype.code, allowed_citype_codes)

    def _prepare_test_file(self, path, content, fs):
        target_dir = os.path.dirname(path) if not path.endswith("/") else path
        try:
            fs.makedirs(target_dir)
        except DirectoryExists:
            pass
        fs.writetext(path, content)


class GeneralRequestResolutionTestSuite(RequestResolutionTestSuite):

    def test_empty_filelist_resolved(self):
        context = get_request_context()
        with self.assertRaises(ResolutionError):
            resolve(DeliveryList([]), context)

    def test_svn_files_resolved(self):
        context = get_request_context(svn_files=["c/file1.txt", "doc/document.pdf"])
        resources = resolve(DeliveryList(["c/file1.txt", "doc/document.pdf"]),
                            context)
        self.assert_request_resolved(resources, context,
                                     clean_svn_files=["c/file1.txt", "doc/document.pdf"])

    def test_private_files_rejected(self):
        PrivateFile(regexp="document").save()
        context = get_request_context(svn_files=["c/file1.txt", "doc/document.pdf"])
        with self.assertRaises(ResolutionError):
            resolve(DeliveryList(["c/file1.txt", "doc/document.pdf"]), context)

    def test_svn_dir_resolved(self):
        context = get_request_context(svn_files=["c/file1.txt", "c/file2.txt"])
        resources = resolve(DeliveryList(["c"]), context)
        self.assert_request_resolved(resources, context,
                                     clean_svn_files=["c/file1.txt", "c/file2.txt"])

    def test_trailing_dot_dir_resolved(self):
        context = get_request_context(svn_files=["c/file1.txt", "c/file2.txt"])
        resources = resolve(DeliveryList(["c/."]), context)
        self.assert_request_resolved(resources, context,
                                     clean_svn_files=["c/file1.txt", "c/file2.txt"])

    def test_leading_dot_dir_resolved(self):
        context = get_request_context(svn_files=["c/file1.txt", "c/file2.txt"])
        resources = resolve(DeliveryList(["./c"]), context)
        self.assert_request_resolved(resources, context,
                                     clean_svn_files=["c/file1.txt", "c/file2.txt"])

    # because path validation is performed on delivery list creation, we can avoid invalid pathes processing
    # def test_fail_on_upper_dir(self):
    # def test_fail_on_root_dir(self):

    def test_fail_on_non_existent_files(self):
        context = get_request_context()
        with self.assertRaises(ResolutionError):
            resolve(DeliveryList(["c/file1.txt", ]), context)

    def test_artifacts_resolved(self):
        context = get_request_context(artifacts=["g:a:v", "g1:a1:v1:zip", "g2:a2:v2:mf"])
        resources = resolve(DeliveryList(["g:a:v", "g1:a1:v1:zip"]), context)
        self.assert_request_resolved(resources, context,
                                     artifacts=["g:a:v",
                                                "g1:a1:v1:zip"])

    def test_fail_on_non_existent_artifacts(self):
        context = get_request_context()
        with self.assertRaises(ResolutionError):
            resolve(DeliveryList(["g:a:v", ]), context)

    def test_same_named_artifacts_separated(self):
        context = get_request_context(artifacts=["com.ow.g1:a:v:zip", "com.ow.g2:a:v:zip",
                                                 "com.ow.g1:a:v:jar"])
        resources = resolve(DeliveryList(["com.ow.g1:a:v:zip", "com.ow.g2:a:v:zip",
                                          "com.ow.g1:a:v:jar"]), context)
        self.assert_request_resolved(resources, context,
                                     artifacts=["com.ow.g1:a:v:zip",
                                                "com.ow.g2:a:v:zip",
                                                "com.ow.g1:a:v:jar"])

    def test_load_from_both_sources(self):
        context = get_request_context(svn_files=["c/file1.txt", "doc/document.pdf"],
                                      artifacts=["g:a:v", "g1:a1:v1:zip", "g2:a2:v2:mf"])
        resources = resolve(DeliveryList(["c/file1.txt", "doc/document.pdf",
                                          "g:a:v", "g1:a1:v1:zip"]), context)
        self.assert_request_resolved(resources, context,
                                     artifacts=["g:a:v",
                                                "g1:a1:v1:zip"],
                                     clean_svn_files=["c/file1.txt", "doc/document.pdf"])

    # this test is disabled since it makes no sense in python3
    def disabled_test_filename_with_russian_symbols_processed(self):
        # actually it is a problem only if russian chars are passed not as type(unicode)
        # 'Россия' in bytes
        rus_bytes = bytearray([0xD0, 0xA0, 0xD0, 0xBE, 0xD1, 0x81,
                               0xD1, 0x81, 0xD0, 0xB8, 0xD1, 0x8F])
        rus_str = str(rus_bytes)
        context = get_request_context(svn_files=["c/file1.txt", "doc/design/Россия"], )
        resources = resolve(DeliveryList([str("doc/design/") + rus_str], ), context)
        self.assert_request_resolved(resources, context,
                                     clean_svn_files=["doc/design/Россия"])

    def test_db_setup_required(self):
        LocTypes.objects.all().delete()
        with self.assertRaises(EnvironmentError):
            BuildRequestResolver()

    def test_duplicates_removed(self):
        context = get_request_context(svn_files=["c/file1.txt"])
        resources = resolve(DeliveryList(["c/file1.txt", "c/file1.txt"]), context)
        self.assert_request_resolved(resources, context, clean_svn_files=["c/file1.txt"])

@mock.patch.dict(os.environ, {'PORTAL_RELEASE_NOTES_ENABLED': 'False'})
class ReleasenotesResolutionTestSuite(RequestResolutionTestSuite):

    def setUp(self):
        super(ReleasenotesResolutionTestSuite, self).setUp()
        category = CiTypeGroups(code="TESTGROUP", name="TESTGROUP", rn_artifactid="foo")
        category.save()
        citype = CiTypes.objects.get(code="ARTIFACT")
        CiTypeIncs(ci_type=citype, ci_type_group=category).save()
        CiRegExp(loc_type=LocTypes.objects.get(code="NXS"),
                 ci_type=citype, regexp="g:a:.+").save()

    #def tearDown(self):
    #    django.core.management.call_command('flush', verbosity=0, interactive=False)

    def test_group_releasenotes_included(self):
        releasenotes_gav = "com.example.rn.sfx.release_notes:foo:v:txt"
        context = get_request_context(artifacts=["g:a:v:zip", releasenotes_gav])
        resources = resolve(DeliveryList(["g:a:v:zip"]), context)
        self.assert_request_resolved(resources, context,
                                     artifacts=["g:a:v:zip", releasenotes_gav])

    def test_releasenotes_included_once(self):
        releasenotes_gav = "com.example.rn.sfx.release_notes:foo:v:txt"
        context = get_request_context(artifacts=["g:a:v:zip", "g2:a:v:zip", releasenotes_gav])
        resources = resolve(DeliveryList(["g:a:v:zip", "g2:a:v:zip"]), context)
        self.assert_request_resolved(resources, context,
                                     artifacts=["g:a:v:zip", "g2:a:v:zip", releasenotes_gav])

    def test_explicit_releasenotes_inclusion_supported(self):
        releasenotes_gav = "com.example.rn.sfx.release_notes:foo:v:txt"
        context = get_request_context(artifacts=["g:a:v:zip", releasenotes_gav])
        resources = resolve(DeliveryList(["g:a:v:zip", releasenotes_gav]), context)
        self.assert_request_resolved(resources, context,
                                     artifacts=["g:a:v:zip", releasenotes_gav])

    def test_group_releasenotes_setup_needed(self):
        CiTypeGroups.objects.filter(code="TESTGROUP").update(rn_artifactid=None)
        releasenotes_gav = "com.example.rn.sfx.release_notes:foo:v:txt"
        context = get_request_context(artifacts=["g:a:v:zip", releasenotes_gav])
        resources = resolve(DeliveryList(["g:a:v:zip"]), context)
        self.assert_request_resolved(resources, context, artifacts=["g:a:v:zip"])

    def test_releasenotes_existence_needed(self):
        releasenotes_gav = "com.example.rn.sfx.release_notes:foo:v:txt"
        context = get_request_context(artifacts=["g:a:v:zip"])
        resources = resolve(DeliveryList(["g:a:v:zip"]), context)
        self.assert_request_resolved(resources, context, artifacts=["g:a:v:zip"])

    def test_filled_citypes_group_needed(self):
        CiTypeGroups.objects.get(code="TESTGROUP").delete()
        releasenotes_gav = "com.example.rn.sfx.release_notes:foo:v:txt"
        context = get_request_context(artifacts=["g:a:v:zip", releasenotes_gav])
        resources = resolve(DeliveryList(["g:a:v:zip"]), context)
        self.assert_request_resolved(resources, context, artifacts=["g:a:v:zip"])

    def test_component_releasenotes_included(self):
        releasenotes_gav = "com.example.rn.sfx.release_notes:foo-bar:v:txt"
        context = get_request_context(artifacts=["g:foo-bar-postfix:v:zip", releasenotes_gav])
        resources = resolve(DeliveryList(["g:foo-bar-postfix:v:zip"]), context)
        self.assert_request_resolved(resources, context,
                                     artifacts=["g:foo-bar-postfix:v:zip", releasenotes_gav])

    def test_component_releasenotes_existence_needed(self):
        releasenotes_gav = "com.example.rn.sfx.release_notes:foo-bar:v:txt"
        context = get_request_context(artifacts=["g:foo-bar-postfix:v:zip"])
        resources = resolve(DeliveryList(["g:foo-bar-postfix:v:zip"]), context)
        self.assert_request_resolved(resources, context,
                                     artifacts=["g:foo-bar-postfix:v:zip"])

    def test_group_releasenotes_prevails_component(self):
        group_releasenotes_gav = "com.example.rn.sfx.release_notes:foo:v:txt"
        component_releasenotes_gav = "com.example.ext.release_notes:foo-bar:v:txt"
        context = get_request_context(artifacts=["g:a:v:zip", group_releasenotes_gav,
                                                 component_releasenotes_gav])
        resources = resolve(DeliveryList(["g:a:v:zip"]), context)
        self.assert_request_resolved(resources, context,
                                     artifacts=["g:a:v:zip", group_releasenotes_gav])

    def test_build_independent_releasenotes_found(self):
        releasenotes1_gav = "com.example.rn.sfx.release_notes:a:v1:txt"
        releasenotes2_gav = "com.example.rn.sfx.release_notes:a:v2:txt"
        context = get_request_context(artifacts=["g:a:v1-123:zip", "g:a:v2-XXX:zip",
                                                 releasenotes1_gav, releasenotes2_gav])

        resources = resolve(DeliveryList(["g:a:v1-123:zip", "g:a:v2-XXX:zip"]), context)
        self.assert_request_resolved(resources, context,
                                     artifacts=["g:a:v1-123:zip", "g:a:v2-XXX:zip",
                                                releasenotes1_gav, releasenotes2_gav])


class SvnDirExpansionTestSuite(RequestResolutionTestSuite):

    def test_empty_dir_expanded(self):
        context = get_request_context(svn_files=["c/"])
        resources = resolve(DeliveryList(["c"]), context)
        self.assert_request_resolved(resources, context, )

    def test_regular_file_kept(self):
        context = get_request_context(svn_files=["c/wrap.txt"])
        resources = resolve(DeliveryList(["c/wrap.txt"]), context)
        self.assert_request_resolved(resources, context, clean_svn_files=["c/wrap.txt"])

    def test_dir_expanded(self):
        context = get_request_context(svn_files=["c/wrap.txt", "c/work/readme.txt"])
        resources = resolve(DeliveryList(["c"]), context)
        self.assert_request_resolved(resources, context, clean_svn_files=["c/wrap.txt",
                                                                          "c/work/readme.txt"])

    def test_slashed_dir_expanded(self):
        context = get_request_context(svn_files=["c/wrap.txt", "c/work/readme.txt"])
        resources = resolve(DeliveryList(["/c"]), context)
        self.assert_request_resolved(resources, context, clean_svn_files=["c/wrap.txt",
                                                                          "c/work/readme.txt"])

    def test_dotted_dir_expanded(self):
        context = get_request_context(svn_files=["c/wrap.txt", "c/work/readme.txt"])
        resources = resolve(DeliveryList(["./c"]), context)
        self.assert_request_resolved(resources, context, clean_svn_files=["c/wrap.txt",
                                                                          "c/work/readme.txt"])
