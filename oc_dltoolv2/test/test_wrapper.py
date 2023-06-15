import os
import django
import posixpath

from . import django_settings

from oc_delivery_apps.checksums.models import LocTypes, CiTypes
from django import test
from oc_delivery_apps.dlmanager.DLModels import DeliveryList
from fs.errors import DirectoryExists
from fs.memoryfs import MemoryFS

from oc_dltoolv2.resolver import BuildRequestResolver
from oc_dltoolv2.resources import RequestContext, LocationStub, DeliveryResource
from oc_dltoolv2.wrapper import Wrapper



class TestFS(MemoryFS):

    def __init__(self, scheme):
        super(TestFS, self).__init__()
        self._scheme = scheme

    def getsyspath(self, path):
        return ((self._scheme + "://" + path) if self._scheme else path)


def get_wrapper():
    return Wrapper(MockWrapper())


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
    return RequestContext(svn_fs, nexus_fs)


def get_resolver():
    return BuildRequestResolver()


class WrappingTestSuite(django.test.TransactionTestCase):

    c_label = '\x63\x61\x72ds'
    d_label = 'd\x77h'
    hdir = 'o\x77s_home'
    wdir = 'o\x77s_\x77ork'
    owner = 'o\x77so\x77ner'

    def setUp(self):
        django.core.management.call_command('migrate', verbosity=0, interactive=False)

        LocTypes(code="SVN", name="SVN").save()
        LocTypes(code="NXS", name="NXS").save()

        CiTypes(code="SVNFILE", name="SVNFILE").save()
        artifacts_citype, _ = CiTypes.objects.get_or_create(code="ARTIFACT", name="ARTIFACT")

        CiTypes(code="RELEASENOTES", name="RELEASENOTES").save()
        CiTypes(code="FILE", name="FILE").save()


    def tearDown(self):
        super().tearDownClass()
        django.core.management.call_command('flush', verbosity=0, interactive=False)

    def _c_cust(self, name):
        return self._c_owner("cust/" + name)

    def _c_owner(self, name):
        return self._owner_file(posixpath.join(self.c_label, self.wdir), name)
    
    def _c_owner_home(self, name):
        return self._owner_file(posixpath.join(self.c_label, self.hdir), name)

    def _d_cust(self, name):
        return self._d_owner("cust/" + name)

    def _d_owner(self, name):
        return self._owner_file(posixpath.join(self.d_label, self.wdir), name)
    
    def _d_owner_home(self, name):
        return self._owner_file(posixpath.join(self.d_label, self.hdir), name)

    def _owner_file(self, folder, filename):
        template = "%s/db/scripts/install/%s%s"
        path = template % (folder, self.owner, "/" + filename if filename else "")
        return path

    def assert_resources_resolved(self, resources, context, clean_svn_files=[], wrapped_svn_files=[]):
        # no renaming should occur
        expected_svn_urls = ["svn://" + path for path in clean_svn_files + wrapped_svn_files]
        actual_svn_urls = [resource.location_stub.path for resource in resources]
        self.assertCountEqual(expected_svn_urls, actual_svn_urls)
        is_same_path = lambda path, resource: resource.location_stub.path.endswith(path)
        matching_resource = lambda path: list (filter(lambda resource: is_same_path(path, resource),
                                                resources) )[0]
        for clean_file in clean_svn_files:
            with matching_resource(clean_file).resource_data.get_content() as content_handle:
                self.assertEqual(clean_file, content_handle.read().decode ('utf-8') )
        for wrapped_file in wrapped_svn_files:
            with matching_resource(wrapped_file).resource_data.get_content() as content_handle:
                self.assertEqual("wrapped", content_handle.read().decode ('utf-8') )

    def test_no_files_to_wrap(self):
        self.maxDiff = None
        context = get_request_context(svn_files=[self._c_cust("c_cust1.sql"),
                                                 self._c_cust("c_cust2.sql"),
                                                 self._d_cust("d_cust1.sql"),
                                                 self._d_cust("d_cust2.sql"), ])
        resolver = get_resolver()
        clean_resources = resolver.resolve_request(DeliveryList([self.c_label, self.d_label]), context)
        resources = get_wrapper().get_wrapped_resources(clean_resources, context.svn_fs)
        self.assert_resources_resolved(resources, context,
                                       clean_svn_files=[self._c_cust("c_cust1.sql"),
                                                        self._c_cust("c_cust2.sql"),
                                                        self._d_cust("d_cust1.sql"),
                                                        self._d_cust("d_cust2.sql"), ])

    def test_only_custs_to_wrap(self):
        context = get_request_context(svn_files=[self._c_cust("c_cust1.sql"),
                                                 self._c_cust("c_cust2.sql"),
                                                 self._d_cust("d_cust1.sql"),
                                                 self._d_cust("d_cust2.sql"), ])
        context.svn_fs.writetext(posixpath.join(self.c_label, "wrap.txt"), "c_cust1.sql\nc_cust2.sql")
        context.svn_fs.writetext(posixpath.join(self.d_label, "wrap.txt"), "d_cust1.sql")

        resolver = get_resolver()
        clean_resources = resolver.resolve_request(DeliveryList([posixpath.join(self.c_label, self.wdir), 
                                                                 posixpath.join(self.d_label, self.wdir)]), context)
        resources = get_wrapper().get_wrapped_resources(clean_resources, context.svn_fs)
        self.assert_resources_resolved(resources, context,
                                       wrapped_svn_files=[self._c_cust("c_cust1.sql"),
                                                          self._c_cust("c_cust2.sql"),
                                                          self._d_cust("d_cust1.sql"), ],
                                       clean_svn_files=[self._d_cust("d_cust2.sql")])

    def test_only_scripts_to_wrap(self):
        context = get_request_context(svn_files=[self._c_owner("c_b.sql"),
                                                 self._c_owner("c_s.sql"),
                                                 self._d_owner("d_b.sql"),
                                                 self._d_owner("d_s.sql"), ])

        resolver = get_resolver()
        clean_resources = resolver.resolve_request(DeliveryList([self.c_label, self.d_label]), context)
        resources = get_wrapper().get_wrapped_resources(clean_resources, context.svn_fs)
        self.assert_resources_resolved(resources, context,
                                       wrapped_svn_files=[self._c_owner("c_b.sql"),
                                                          self._d_owner("d_b.sql"), ],
                                       clean_svn_files=[self._c_owner("c_s.sql"),
                                                        self._d_owner("d_s.sql"), ])
    
    def test_only_home_scripts_to_wrap(self):
        context = get_request_context(svn_files=[self._c_owner_home("c_b.sql"),
                                                 self._c_owner_home("c_s.sql"),
                                                 self._d_owner_home("d_b.sql"),
                                                 self._d_owner_home("d_s.sql"), ])

        resolver = get_resolver()
        clean_resources = resolver.resolve_request(DeliveryList([self.c_label, self.d_label]), context)
        resources = get_wrapper().get_wrapped_resources(clean_resources, context.svn_fs)
        self.assert_resources_resolved(resources, context,
                                       wrapped_svn_files=[self._c_owner_home("c_b.sql"),
                                                          self._d_owner_home("d_b.sql"), ],
                                       clean_svn_files=[self._c_owner_home("c_s.sql"),
                                                        self._d_owner_home("d_s.sql"), ])
    
    def test_home_and_work_scripts_to_wrap(self):
        context = get_request_context(svn_files=[self._c_owner_home("c_b.sql"),
                                                 self._c_owner_home("c_s.sql"),
                                                 self._c_owner("cc_b.sql"),
                                                 self._c_owner("cc_s.sql"),
                                                 self._d_owner_home("d_b.sql"),
                                                 self._d_owner_home("d_s.sql"), 
                                                 self._d_owner("dd_b.sql"),
                                                 self._d_owner("dd_s.sql"), ])

        resolver = get_resolver()
        clean_resources = resolver.resolve_request(DeliveryList([posixpath.join(self.c_label, self.hdir), 
                                                                 posixpath.join(self.d_label, self.hdir), 
                                                                 posixpath.join(self.c_label, self.wdir),
                                                                 posixpath.join(self.d_label, self.wdir)]), context)
        resources = get_wrapper().get_wrapped_resources(clean_resources, context.svn_fs)
        self.assert_resources_resolved(resources, context,
                                       wrapped_svn_files=[self._c_owner_home("c_b.sql"),
                                                          self._c_owner("cc_b.sql"), 
                                                          self._d_owner_home("d_b.sql"),
                                                          self._d_owner("dd_b.sql"), ],
                                       clean_svn_files=[self._c_owner_home("c_s.sql"),
                                                        self._c_owner("cc_s.sql"),
                                                        self._d_owner_home("d_s.sql"),
                                                        self._d_owner("dd_s.sql"), ])

    def test_wrap_files_from_both_sources(self):
        context = get_request_context(svn_files=[self._c_cust("c_cust1.sql"),
                                                 self._c_cust("c_cust2.sql"),
                                                 self._d_cust("d_cust1.sql"),
                                                 self._d_cust("d_cust2.sql"),
                                                 self._c_owner("c_b.sql"),
                                                 self._c_owner("c_s.sql"),
                                                 self._d_owner("d_b.sql"),
                                                 self._d_owner("d_s.sql"), ])
        context.svn_fs.writetext(posixpath.join(self.c_label, "wrap.txt"), "c_cust1.sql\nc_cust2.sql")
        context.svn_fs.writetext(posixpath.join(self.d_label, "wrap.txt"), "d_cust1.sql")

        resolver = get_resolver()
        clean_resources = resolver.resolve_request(DeliveryList([posixpath.join(self.c_label, self.wdir),
                                                                 posixpath.join(self.d_label, self.wdir)]), context)
        resources = get_wrapper().get_wrapped_resources(clean_resources, context.svn_fs)
        self.assert_resources_resolved(resources, context,
                                       wrapped_svn_files=[self._c_owner("c_b.sql"),
                                                          self._d_owner("d_b.sql"),
                                                          self._c_cust("c_cust1.sql"),
                                                          self._c_cust("c_cust2.sql"),
                                                          self._d_cust("d_cust1.sql"), ],
                                       clean_svn_files=[self._c_owner("c_s.sql"),
                                                        self._d_owner("d_s.sql"),
                                                        self._d_cust("d_cust2.sql")])

    def test_wrong_wrapfile_case_corrected(self):
        context = get_request_context(svn_files=[self._c_cust("FilE1.Sql"),
                                                 self._c_cust("FILE2.SQL"), ])
        context.svn_fs.writetext(posixpath.join(self.c_label, "wrap.txt"), "file1.sql\nfile2.sql")

        resolver = get_resolver()
        clean_resources = resolver.resolve_request(DeliveryList([posixpath.join(self.c_label, self.wdir)]), context)
        resources = get_wrapper().get_wrapped_resources(clean_resources, context.svn_fs)
        self.assert_resources_resolved(resources, context,
                                       wrapped_svn_files=[self._c_cust("FilE1.Sql"),
                                                          self._c_cust("FILE2.SQL"), ], )

    def test_wrong_owner_scripts_case_corrected(self):
        context = get_request_context(svn_files=[self._c_owner("c_b.sql"),
                                                 self._c_owner("c_s.sql"),
                                                 self._d_owner("d_B.SQL"),
                                                 self._d_owner("d_s.Sql"), ])

        resolver = get_resolver()
        clean_resources = resolver.resolve_request(DeliveryList([self.c_label, self.d_label]), context)
        resources = get_wrapper().get_wrapped_resources(clean_resources, context.svn_fs)
        self.assert_resources_resolved(resources, context,
                                       wrapped_svn_files=[self._c_owner("c_b.sql"),
                                                          self._d_owner("d_B.SQL"), ],
                                       clean_svn_files=[self._c_owner("c_s.sql"),
                                                        self._d_owner("d_s.Sql"), ])

    def test_extra_spaces_in_wrapfile_ignored(self):
        context = get_request_context(svn_files=[self._c_cust("c_cust1.sql"),
                                                 self._c_cust("c_cust2.sql"), ])
        context.svn_fs.writetext(posixpath.join(self.c_label, "wrap.txt"), "c_cust1.sql \n c_cust2.sql   ")

        resolver = get_resolver()
        clean_resources = resolver.resolve_request(DeliveryList([posixpath.join(self.c_label, self.wdir)]), context)
        resources = get_wrapper().get_wrapped_resources(clean_resources, context.svn_fs)
        self.assert_resources_resolved(resources, context,
                                       wrapped_svn_files=[self._c_cust("c_cust1.sql"),
                                                          self._c_cust("c_cust2.sql"), ])

    def test_extra_wrapfile_items_skipped(self):
        context = get_request_context(svn_files=[self._c_cust("c_cust1.sql"),
                                                 self._c_cust("c_cust2.sql"), ])
        context.svn_fs.writetext(posixpath.join(self.c_label, "wrap.txt"), "c_cust1.sql\nc_cust2.sql\nc_cust3.sql")

        resolver = get_resolver()
        clean_resources = resolver.resolve_request(DeliveryList([posixpath.join(self.c_label, self.wdir)]), context)
        resources = get_wrapper().get_wrapped_resources(clean_resources, context.svn_fs)
        self.assert_resources_resolved(resources, context,
                                       wrapped_svn_files=[self._c_cust("c_cust1.sql"),
                                                          self._c_cust("c_cust2.sql"), ])

    def test_empty_wrapfile_processed(self):
        context = get_request_context(svn_files=[self._c_cust("c_cust1.sql"),
                                                 self._c_cust("c_cust2.sql"), ])
        context.svn_fs.writetext(posixpath.join(self.c_label, "wrap.txt"), "")

        resolver = get_resolver()
        clean_resources = resolver.resolve_request(DeliveryList([posixpath.join(self.c_label, self.wdir)]), context)
        resources = get_wrapper().get_wrapped_resources(clean_resources, context.svn_fs)
        self.assert_resources_resolved(resources, context,
                                       clean_svn_files=[self._c_cust("c_cust1.sql"),
                                                        self._c_cust("c_cust2.sql"), ])

    def test_cust_name_containing_spaces_processed(self):
        context = get_request_context(svn_files=[self._c_cust("cust 1 .sql"),
                                                 self._c_cust("other cust.sql"), ])
        context.svn_fs.writetext(posixpath.join(self.c_label, "wrap.txt"), "cust 1 .sql")

        resolver = get_resolver()
        clean_resources = resolver.resolve_request(DeliveryList([posixpath.join(self.c_label, self.wdir)]), context)
        resources = get_wrapper().get_wrapped_resources(clean_resources, context.svn_fs)
        self.assert_resources_resolved(resources, context,
                                       clean_svn_files=[self._c_cust("other cust.sql"), ],
                                       wrapped_svn_files=[self._c_cust("cust 1 .sql")])

    def test_other_loctypes_skipped(self):
        context = get_request_context(svn_files=[self._c_cust("c_cust1.sql"),
                                                 self._c_cust("c_cust2.sql"),
                                                 self._d_cust("d_cust1.sql"),
                                                 self._d_cust("d_cust2.sql"), ])
        context.svn_fs.writetext(posixpath.join(self.c_label, "wrap.txt"), "c_cust1.sql\nc_cust2.sql")
        context.svn_fs.writetext(posixpath.join(self.d_label, "wrap.txt"), "d_cust1.sql")
        test_loctype = LocTypes(code="TEST", name="TEST")
        test_loctype.save()

        resolver = get_resolver()
        clean_resources = resolver.resolve_request(DeliveryList([posixpath.join(self.c_label, self.wdir), 
                                                                 posixpath.join(self.d_label, self.wdir)]), context)
        c_cust2 = list (filter(lambda resource: resource.location_stub.path.endswith("c_cust2.sql"),
                             clean_resources) ) [0]
        clean_resources.remove(c_cust2)
        prev_location = c_cust2.location_stub
        new_location = LocationStub(test_loctype, CiTypes.objects.get(code="FILE"),
                                    prev_location.path, prev_location.revision)
        new_resource = DeliveryResource(new_location, c_cust2.resource_data)
        clean_resources.append(new_resource)
        resources = get_wrapper().get_wrapped_resources(clean_resources, context.svn_fs)

        self.assert_resources_resolved(resources, context,
                                       wrapped_svn_files=[self._c_cust("c_cust1.sql"),
                                                          self._d_cust("d_cust1.sql"), ],
                                       clean_svn_files=[self._d_cust("d_cust2.sql"),
                                                        self._c_cust("c_cust2.sql"),
                                                        ])


class MockWrapper(object):

    def wrap_file(self, fs, file_path):
        fs.writetext(file_path, "wrapped")
