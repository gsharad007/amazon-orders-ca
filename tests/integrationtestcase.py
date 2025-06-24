__copyright__ = "Copyright (c) 2024-2025 Alex Laird"
__license__ = "MIT"

import os
import sys
import time
import unittest

from amazonorders import conf
from amazonorders.conf import AmazonOrdersConfig
from amazonorders.orders import AmazonOrders
from amazonorders.session import AmazonSession
from amazonorders.transactions import AmazonTransactions
from tests.testcase import TestCase


class IntegrationTestCase(TestCase):
    """
    This test class will prompt for challenges (2FA, Captcha) as necessary. To run fully automated (assuming
    no Captcha prompts are encountered), set all authentication environment variables:

    - AMAZON_USERNAME
    - AMAZON_PASSWORD
    - AMAZON_OTP_SECRET_KEY (optional, if 2FA is enabled for the account)
    """

    amazon_session = None

    @classmethod
    def setUpClass(cls):
        cls.set_up_class_conf()

        cls.debug = os.environ.get("DEBUG", "False") == "True"
        cls.amazon_session = AmazonSession(debug=cls.debug,
                                           config=cls.test_config)
        cls.amazon_session.login()

        cls.amazon_orders = AmazonOrders(cls.amazon_session)
        cls.amazon_transactions = AmazonTransactions(cls.amazon_session)

    @classmethod
    def tearDownClass(cls):
        # Slow down between integration suites to ensure we don't trigger Amazon to throttle or lock the account
        time.sleep(cls.reauth_sleep_time)

    @classmethod
    def set_up_class_conf(cls):
        # An OTP is only valid for one login, so when an account is using 2FA, ensure extra sleep between tests to
        # ensure the next token has been generated
        cls.reauth_sleep_time = 3 if "AMAZON_OTP_SECRET_KEY" not in os.environ else 61

        if not (
            os.environ.get("AMAZON_USERNAME") and os.environ.get("AMAZON_PASSWORD")
        ):
            raise unittest.SkipTest(
                "AMAZON_USERNAME and AMAZON_PASSWORD environment variables must be set to run integration tests"
            )

        conf.DEFAULT_CONFIG_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), ".integration-config")
        test_output_dir = os.path.join(conf.DEFAULT_CONFIG_DIR, "output")
        test_cookie_jar_path = os.path.join(conf.DEFAULT_CONFIG_DIR, "cookies.json")
        cls.test_config = AmazonOrdersConfig(data={
            "output_dir": test_output_dir,
            "cookie_jar_path": test_cookie_jar_path
        })

        if os.path.exists(test_cookie_jar_path):
            os.remove(test_cookie_jar_path)

    def setUp(self):
        self.assertTrue(self.amazon_session.is_authenticated)
