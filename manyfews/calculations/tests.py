from django.test import TestCase

# Create your tests here.
from .models import ZentraReading
from .tasks import prepareZentra

from django.test import TestCase


class WeatherImportTests(TestCase):
    def test_fetch_from_zentra(self):
        prepareZentra()


#        readings = ZentraReading.objects.all()
#        assert len(readings) > 0
