import unittest
from datetime import datetime

from .. import delivery_attributes
from ..DeliveryValidations import ValidationException


class DeliveryAttributesGenerationTestSuite(unittest.TestCase):

    def test_new_version_generation(self):
        timestamp = datetime(year=2001, month=2, day=3)
        minor = None
        expected = "v20010203"
        generated = delivery_attributes.generate_version(timestamp, minor)
        self.assertEqual(expected, generated)

    def test_version_date_with_minor(self):
        timestamp = datetime(year=2001, month=2, day=3)
        minor = 4
        expected = "v20010203_4"
        generated = delivery_attributes.generate_version(timestamp, minor)
        self.assertEqual(expected, generated)

    def test_artifactid_extraction(self):
        branch = "branches/prj-testproj"
        generated = delivery_attributes.extract_artifactid(branch)
        self.assertEqual("testproj", generated)

    def test_artifactid_containing_prj_extraction(self):
        # there are some tags like prj-prj-...
        branch = "branches/prj-prj-testproj"
        generated = delivery_attributes.extract_artifactid(branch)
        self.assertEqual("prj-testproj", generated)

    def test_invalid_branch_missing_artifactid(self):
        # there are some tags like prj-prj-...
        branch = "branches/int"
        with self.assertRaises(ValidationException):
            delivery_attributes.extract_artifactid(branch)

    def test_project_type_extracted(self):
        branch = "branches/hf-hotfix"
        extracted = delivery_attributes.extract_project_type(branch)
        self.assertEqual("hf", extracted)

    def test_trunk_is_project(self):
        branch = "trunk"
        extracted = delivery_attributes.extract_project_type(branch)
        self.assertEqual("prj", extracted)

    def test_int_is_project(self):
        branch = "int"
        extracted = delivery_attributes.extract_project_type(branch)
        self.assertEqual("prj", extracted)

    def test_tag_url_generation(self):
        generated = delivery_attributes.generate_tag_url("svn/Russia/RUSTEST",
                                                         "hf", "RUSTEST-project", "v1.1")
        expected = "svn/Russia/RUSTEST/tags/hf-RUSTEST-project-v1.1"
        self.assertEqual(expected, generated)
