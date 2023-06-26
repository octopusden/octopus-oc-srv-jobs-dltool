from . import django_settings
from configobj import ConfigObj
from django import test
from oc_delivery_apps.dlmanager.models import Delivery
from ..db_steps import delivery_is_in_db
import django


class TestRecordInDb(test.TransactionTestCase):
    def setUp(self):
        django.core.management.call_command('migrate', verbosity=0, interactive=False)
        test_delivery = Delivery()
        test_delivery.groupid = "g"
        test_delivery.artifactid = "a"
        test_delivery.version = "v1"
        test_delivery.save()

    def tearDown(self):
        django.core.management.call_command('flush', verbosity=0, interactive=False)

    def test_delivery_exists(self):
        delivery_params = ConfigObj()
        delivery_params["groupid"] = "g"
        delivery_params["artifactid"] = "a"
        delivery_params["version"] = "v1"

        self.assertEqual(delivery_is_in_db(delivery_params), True)

    def test_delivery_not_exists(self):
        delivery_params = ConfigObj()
        delivery_params["groupid"] = "g"
        delivery_params["artifactid"] = "a"
        delivery_params["version"] = "v2"

        self.assertEqual(delivery_is_in_db(delivery_params), False)
