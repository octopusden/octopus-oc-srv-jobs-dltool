import os
import unittest
from unittest.mock import patch

from ..dlbuild_worker import load_vault_credentials


class LoadVaultCredentialsTestSuite(unittest.TestCase):

    @patch.dict(os.environ, {"MVN_PASSWORD": "from-env"}, clear=True)
    @patch("oc_dltoolv2.dlbuild_worker.VaultAPI.VaultAPI")
    def test_environment_wins_over_vault(self, vault_api):
        vault_api.return_value.load_secret.return_value = "from-vault"
        load_vault_credentials()
        self.assertEqual("from-env", os.environ["MVN_PASSWORD"])
        asked = [_call.args[0] for _call in vault_api.return_value.load_secret.call_args_list]
        self.assertNotIn("MVN__PASSWORD", asked)

    @patch.dict(os.environ, {}, clear=True)
    @patch("oc_dltoolv2.dlbuild_worker.VaultAPI.VaultAPI")
    def test_missing_value_is_taken_from_vault(self, vault_api):
        vault_api.return_value.load_secret.side_effect = lambda name: "from-vault" if name == "MVN__PASSWORD" else None
        load_vault_credentials()
        self.assertEqual("from-vault", os.environ["MVN_PASSWORD"])

    @patch.dict(os.environ, {}, clear=True)
    @patch("oc_dltoolv2.dlbuild_worker.VaultAPI.VaultAPI")
    def test_value_missing_everywhere_stays_unset(self, vault_api):
        vault_api.return_value.load_secret.return_value = None
        load_vault_credentials()
        self.assertNotIn("PSQL_MQ_URL", os.environ)
        self.assertNotIn("AMQP_PASSWORD", os.environ)

    @patch.dict(os.environ, {}, clear=True)
    @patch("oc_dltoolv2.dlbuild_worker.VaultAPI.VaultAPI")
    def test_every_credential_is_looked_up(self, vault_api):
        vault_api.return_value.load_secret.return_value = None
        load_vault_credentials()
        asked = [_call.args[0] for _call in vault_api.return_value.load_secret.call_args_list]
        for name in ["PSQL", "PSQL_MQ", "AMQP", "MVN", "SVN", "SVN_CLIENTS", "SMTP"]:
            for key in ["URL", "USER", "PASSWORD"]:
                self.assertIn("%s__%s" % (name, key), asked)
