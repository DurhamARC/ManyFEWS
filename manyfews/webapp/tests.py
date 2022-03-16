import re
from time import sleep

from django.contrib.gis.geos import Polygon
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase, LiveServerTestCase
from selenium import webdriver
from selenium.webdriver.common.by import By
from .converters import BoundingBoxUrlParameterConverter


class ConverterTestCase(TestCase):
    def test_bounding_box_url_parameter_converter(self):
        converter = BoundingBoxUrlParameterConverter()

        # Check conversion to bounding box
        # Simple ints
        bb = converter.to_python("1,2,3,4")
        assert bb == Polygon.from_bbox((1, 2, 3, 4))

        # Negative numbers and decimals
        bb = converter.to_python("-1,2.345,-3.456789,4")
        assert bb == Polygon.from_bbox((-1, 2.345, -3.456789, 4))

        # Invalid types
        self.assertRaises(ValueError, converter.to_python, "-1,2.345,-3.456789,4,5,6,7")
        self.assertRaises(ValueError, converter.to_python, "not,a,valid,coordinate")

        # Check regex works as expected
        assert re.fullmatch(converter.regex, "1,2,3,4")
        assert re.fullmatch(converter.regex, "-1,2.345,-3.456789,4")
        assert not re.fullmatch(converter.regex, "1,2")
        assert not re.fullmatch(converter.regex, "1,2-")
        assert not re.fullmatch(converter.regex, "not,a,valid,coordinate")


class WebAppTestCase(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        cls.selenium = webdriver.Chrome(options=options)
        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def test_home(self):
        # Simple test that the home page loads without errors
        self.selenium.get("%s%s" % (self.live_server_url, "/"))

        # Should be 10 daily risk boxes
        daily_risk_elements = self.selenium.find_elements(By.CLASS_NAME, "daily-risk")
        assert len(daily_risk_elements) == 10
        # Each should contain 4 hourly risk boxes
        for el in daily_risk_elements:
            hourly_risk_elements = el.find_elements(By.CLASS_NAME, "risk")
            assert len(hourly_risk_elements) == 4

        # Click on an hourly risk to ensure no errors on loading new map layers
        daily_risk_elements[1].find_element(By.CLASS_NAME, "risk").click()
        sleep(1)

        log = self.selenium.get_log("browser")
        assert len(log) == 0, "Errors in browser log:\n" + "\n".join(
            [f"{line['level']}: {line['message']}" for line in log]
        )

    def test_users(self):
        # Add a user, log in, log out
        self.selenium.get("%s%s" % (self.live_server_url, "/accounts/signup/"))

        # Check top-right buttons are "Login" and "Sign up"
        buttons = self.selenium.find_elements_by_css_selector(".header .col-2 .btn")
        assert len(buttons) == 2
        assert buttons[0].text == "Login"
        assert buttons[1].text == "Sign Up"

        self.selenium.find_element_by_id("id_username").send_keys("myuser")
        self.selenium.find_element_by_id("id_password1").send_keys("al25ns5235")
        self.selenium.find_element_by_id("id_password2").send_keys("al25ns5235")
        self.selenium.find_element_by_id("signup-submit").click()

        assert self.selenium.current_url == "%s%s" % (
            self.live_server_url,
            "/accounts/login/",
        )
        self.selenium.find_element_by_id("id_username").send_keys("myuser")
        self.selenium.find_element_by_id("id_password").send_keys("al25ns5235")
        self.selenium.find_element_by_id("login-submit").click()

        assert self.selenium.current_url == "%s%s" % (self.live_server_url, "/")
        buttons = self.selenium.find_elements_by_css_selector(".header .col-2 .btn")
        assert len(buttons) == 1
        assert buttons[0].text == "Log Out"
