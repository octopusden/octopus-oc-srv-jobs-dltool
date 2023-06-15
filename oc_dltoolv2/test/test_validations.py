import unittest

from oc_dltoolv2 import DeliveryValidations as validations


class DlNameLogicTester(unittest.TestCase):

    def test_empty_artifactid(self):
        artifactid = ""
        branch_from = "branches/prj-CLIENT-TTT-20131205"
        client = "CLIENT"
        with self.assertRaises(validations.ValidationException):
            validations.validate_artifactid(artifactid, client, branch_from)

    def test_project_matching_artifactid(self):
        artifactid = "SOME_PROJECT"
        client = "CLIENT"
        branch_from = "branches/prj-SOME_PROJECT"
        self.assertTrue(validations.validate_artifactid(artifactid, client, branch_from))

    def test_client_project_artifactid(self):
        artifactid = "CLIENT-SOME_PROJECT"
        branch_from = "branches/prj-project"
        client = "CLIENT"
        self.assertTrue(validations.validate_artifactid(artifactid, client, branch_from))

    def test_invalid_artifactid(self):
        artifactid = "SOME_PROJECT"
        branch_from = "branches/prj-project"
        client = "CLIENT"
        with self.assertRaises(validations.ValidationException):
            self.assertTrue(validations.validate_artifactid(artifactid, client, branch_from))

    def test_incorrect_client_for_int(self):
        artifactid = "OTHERCLIENT-TTT-20160701_2"
        branch_from = "branches/int"
        client = "CLIENT"
        with self.assertRaises(validations.ValidationException):
            validations.validate_artifactid(artifactid, client, branch_from)

    def test_project_name_for_int(self):
        artifactid = "OTHERCLIENT-TTT-20160701_2"
        branch_from = "branches/int"
        client = "OTHERCLIENT"
        self.assertTrue(validations.validate_artifactid(artifactid, client, branch_from))

    def test_name_with_dashed_v(self):
        artifactid = "CLIENT-vup"
        project_branch = "branches/prj-CLIENT-vup"
        client = "CLIENT"
        self.assertTrue(validations.validate_artifactid(artifactid, client, project_branch))

    def test_missing_project_name(self):
        artifactid = "CLIENT-"
        project_branch = "branches/int"
        client = "CLIENT"
        with self.assertRaises(validations.ValidationException):
            validations.validate_artifactid(artifactid, client, project_branch)

    def test_invalid_characters(self):
        artifactid = "CLIENT-название"
        project_branch = "branches/int"
        client = "CLIENT"
        with self.assertRaises(validations.ValidationException):
            validations.validate_artifactid(artifactid, client, project_branch)

    def test_jira_issue_name(self):
        artifactid = "JIRA-123"
        project_branch = "branches/int"
        client = "CLIENT"
        self.assertTrue(validations.validate_artifactid(artifactid, client, project_branch))

    def test_jira_issue_separator_required(self):
        artifactid = "JIRA123"
        project_branch = "branches/int"
        client = "CLIENT"
        with self.assertRaises(validations.ValidationException):
            self.assertTrue(validations.validate_artifactid(artifactid, client, project_branch))

    def test_jira_issue_number_required(self):
        artifactid = "JIRA-"
        project_branch = "branches/int"
        client = "CLIENT"
        with self.assertRaises(validations.ValidationException):
            self.assertTrue(validations.validate_artifactid(artifactid, client, project_branch))

    def test_jira_issue_group_only_capitalized(self):
        artifactid = "Jira-123"
        project_branch = "branches/int"
        client = "CLIENT"
        with self.assertRaises(validations.ValidationException):
            self.assertTrue(validations.validate_artifactid(artifactid, client, project_branch))


class IDTNamesTestSuite(unittest.TestCase):

    def test_correct_name_from_idt(self):
        artifactid = "I1234321"
        branch_from = "branches/int"
        client = "CLIENT"
        self.assertTrue(validations.validate_artifactid(artifactid, client, branch_from))

    def test_non_project_branch_types_detection(self):
        artifactid = "I1234321"
        non_project_branches = ["branches/int", "branches/hf-abc", "branches/mig-03.43.2", "trunk"]
        client = "CLIENT"
        self.assertTrue(all(
            [validations.validate_artifactid(artifactid, client, b) for b in non_project_branches]))

    def test_project_branch_with_idt(self):
        artifactid = "I1234321"
        project_branch = "branches/prj-CLIENT"
        client = "CLIENT"
        self.assertTrue(validations.validate_artifactid(artifactid, client, project_branch))


class DeliveryVersionTestSuite(unittest.TestCase):

    def test_empty_version(self):
        version = ""
        with self.assertRaises(validations.ValidationException):
            validations.validate_version(version)

    def test_correct_version(self):
        version = "v20110203_04"
        self.assertTrue(validations.validate_version(version))

    def test_version_contains_letters(self):
        version = "v2016XXX05_05"
        with self.assertRaises(validations.ValidationException):
            validations.validate_version(version)

    def test_version_startswith_number(self):
        version = "20_v20110203_04"
        with self.assertRaises(validations.ValidationException):
            validations.validate_version(version)

    def test_version_without_prefix(self):
        version = "20110203_04"
        with self.assertRaises(validations.ValidationException):
            validations.validate_version(version)

    def test_version_with_dot(self):
        version = "v20110203_04.05"
        self.assertTrue(validations.validate_version(version))


class FullDeliveryNameTestSuite(unittest.TestCase):

    def test_empty_delivery_name(self):
        delivery_name = ""
        branch = "branches/prj-CLIENT-TTT-20131205"
        client = "CLIENT"
        with self.assertRaises(validations.ValidationException):
            validations.validate_delivery_name(delivery_name, client, branch)

    def test_correct_delivery_name(self):
        delivery_name = "CLIENT-TTT-v20110203"
        branch_from = "branches/prj-CLIENT-TTT"
        client = "CLIENT"
        validations.validate_delivery_name(delivery_name, client, branch_from)

    def test_incorrect_artifactid(self):
        delivery_name = "XXX-TTT-v20131205"
        branch_from = "branches/prj-CLIENT-TTT-20131205"
        client = "CLIENT"
        with self.assertRaises(validations.ValidationException):
            validations.validate_delivery_name(delivery_name, client, branch_from)

    def test_incorrect_version(self):
        delivery_name = "CLIENT-TTT-v201312XXX"
        branch_from = "branches/prj-CLIENT-TTT-20131205"
        client = "CLIENT"
        with self.assertRaises(validations.ValidationException):
            validations.validate_delivery_name(delivery_name, client, branch_from)

    def test_no_version_separated(self):
        delivery_name = "CLIENT-TTT-20110203_04"
        branch_from = "branches/prj-CLIENT-TTT-20131205"
        client = "CLIENT"
        with self.assertRaises(validations.ValidationException):
            validations.validate_delivery_name(delivery_name, client, branch_from)
