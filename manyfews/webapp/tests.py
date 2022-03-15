import re

from django.contrib.gis.geos import Polygon
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase, LiveServerTestCase
from selenium import webdriver
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

        risk_elements = self.selenium.find_elements_by_class_name("daily-risk")
        assert len(risk_elements) == 7

        risk_elements[1].click()

        log = self.selenium.get_log("browser")
        assert len(log) == 0, "Errors in browser log:\n" + "\n".join(
            [f"{line['level']}: {line['message']}" for line in log]
        )
