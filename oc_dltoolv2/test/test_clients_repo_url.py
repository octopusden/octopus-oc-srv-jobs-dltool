import os
import unittest
from unittest.mock import patch

from ..build_delivery_from_queue import get_clients_repo_url


class ClientsRepoUrlTestSuite(unittest.TestCase):

    @patch.dict(os.environ, {"SVN_CLIENTS_REPO": "test_02"}, clear=True)
    def test_repo_is_appended_to_svn_url(self):
        self.assertEqual("https://svn.example.com/svn/test_02",
                         get_clients_repo_url("https://svn.example.com/svn"))

    @patch.dict(os.environ, {"SVN_CLIENTS_REPO": "/test_02/"}, clear=True)
    def test_slashes_are_not_doubled(self):
        self.assertEqual("https://svn.example.com/svn/test_02",
                         get_clients_repo_url("https://svn.example.com/svn/"))

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_repo_raises(self):
        with self.assertRaises(ValueError):
            get_clients_repo_url("https://svn.example.com/svn")
