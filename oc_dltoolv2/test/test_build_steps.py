from . import django_settings
import django
from django import test
from unittest.mock import patch
from io import BytesIO
from oc_delivery_apps.checksums.models import CiTypes, CsTypes, LocTypes, CiRegExp
from ..build_steps import calculate_and_check_checksums
from ..distributives_api_client import DistributivesAPIClient
from ..resources import DeliveryResource, LocationStub, ResourceData
from .mocks import mocked_requests
from ..delivery_exceptions import DeliveryDeniedException


class TestResourceData(ResourceData):
    def __init__(self, is_allowed=True, not_found=False, svn_path=False, allowed_parent=False, forbidden_parent=False):
        self.is_allowed = is_allowed
        self.not_found = not_found
        self.svn_path = svn_path
        self.allowed_parent = allowed_parent
        self.forbidden_parent = forbidden_parent


    def get_content(self):
        if self.is_allowed and not self.not_found and not self.svn_path and not self.allowed_parent and not self.forbidden_parent:
            return BytesIO("content".encode("utf8"))
        elif self.not_found:
            return BytesIO("not_found".encode("utf8"))
        elif self.svn_path:
            return BytesIO("svn_path".encode("utf8"))
        elif self.allowed_parent:
            return BytesIO("allowed_parent".encode("utf8"))
        elif self.forbidden_parent:
            return BytesIO("forbidden_parent".encode("utf8"))
        else:
            return BytesIO("not_allowed_content".encode("utf8"))

class BuildStepsTestSuite(django.test.TransactionTestCase):
    def setup_resources(self):
        allowed_location = LocationStub("NXS:Nexus artifact", "TESTDSTR", "gg1:aa1:vv1", "rev")
        allowed_resource = DeliveryResource(
            allowed_location, TestResourceData())

        not_allowed_location = LocationStub("NXS:Nexus artifact", "TESTNXSDSTR", "gg:aa:vv", "rev")
        not_allowed_resource=DeliveryResource(
            not_allowed_location, TestResourceData(is_allowed=False))

        not_found_location = LocationStub("NXS:Nexus artifact", "TESTDSTR", "gg2:aa2:vv2", "rev")
        not_found_resource=DeliveryResource(
            not_found_location, TestResourceData(not_found=True))

        svn_path_location = LocationStub("SVN:SubVersion revision", "TESTSVNDSTR", "http://some_svn/distr/file.sql", "rev")
        svn_path_resource=DeliveryResource(
            svn_path_location, TestResourceData(svn_path=True))

        allowed_location_with_allowed_parent = LocationStub("NXS:Nexus artifact", "TESTDSTR", "gg3:aa3:vv3", "rev")
        allowed_resource_with_allowed_parent = DeliveryResource(
            allowed_location_with_allowed_parent, TestResourceData(allowed_parent=True))

        allowed_location_with_forbidden_parent = LocationStub("NXS:Nexus artifact", "TESTDSTR", "gg5:aa5:vv5", "rev")
        allowed_resource_with_forbidden_parent = DeliveryResource(
            allowed_location_with_forbidden_parent, TestResourceData(forbidden_parent=True))

        return allowed_resource, not_allowed_resource, not_found_resource, svn_path_resource, allowed_resource_with_allowed_parent, allowed_resource_with_forbidden_parent

    def setUp(self):
        django.core.management.call_command('migrate', verbosity=0, interactive=False)
        self.api= DistributivesAPIClient(api_url = "http://distro-api-test")
        self.allowed_resource, self.not_allowed_resource, self.not_found_resource, self.svn_path_resource, self.allowed_resource_with_allowed_parent, self.allowed_resource_with_forbidden_parent = self.setup_resources()

    def tearDown(self):
        django.core.management.call_command('flush', verbosity=0, interactive=False)

    @patch('requests.get', side_effect = mocked_requests)
    def test_calculate_and_check_checksums_success(self, mocked_requests):
        resources=[self.allowed_resource]
        checksums_list=calculate_and_check_checksums(resources, self.api)
        self.assertEqual(checksums_list[0]["checksum"], "9a0364b9e99bb480dd25e1f0284c8555")

    @patch('requests.get', side_effect = mocked_requests)
    def test_calculate_and_check_checksums_distributive_not_allowed_failure(self, mocked_requests):
        resources=[self.allowed_resource, self.not_allowed_resource]
        with self.assertRaises(DeliveryDeniedException):
            checksums_list=calculate_and_check_checksums(resources, self.api)

    @patch('requests.get', side_effect = mocked_requests)
    def test_calculate_and_check_checksums_distributive_not_found_success(self, mocked_requests):
        # For more consistency we assume that not found distrubutives are allowed for delivery
        resources=[self.not_found_resource]
        checksums_list=calculate_and_check_checksums(resources, self.api)
        self.assertEqual(checksums_list[0]["checksum"], "7500611bf7030bc99d25c354e7b64714")

    @patch('requests.get', side_effect = mocked_requests)
    def test_calculate_and_check_checksums_svn_and_nxs_distributives_checked_in_api(self, mocked_requests):
        resources=[self.svn_path_resource, self.allowed_resource]
        checksums_list=calculate_and_check_checksums(resources, self.api)
        self.assertEqual(checksums_list[0]["checksum"], "d4c9a5389f90d6968f1c2515203f760c")
        self.assertEqual(checksums_list[1]["checksum"], "9a0364b9e99bb480dd25e1f0284c8555")

    @patch('requests.get', side_effect = mocked_requests)
    def test_calculate_and_check_checksums_distributive_parent_allowed_success(self, mocked_requests):
        resources=[self.allowed_resource_with_allowed_parent]
        checksums_list=calculate_and_check_checksums(resources, self.api)
        self.assertEqual(checksums_list[0]["checksum"], "6a185fceb4045453d7fddc9cf2c0820c")

    @patch('requests.get', side_effect = mocked_requests)
    def test_calculate_and_check_checksums_distributive_parent_not_allowed_failure(self, mocked_requests):
        resources=[self.allowed_resource_with_forbidden_parent]
        with self.assertRaises(DeliveryDeniedException):
            checksums_list=calculate_and_check_checksums(resources, self.api)
