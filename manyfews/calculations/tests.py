from django.contrib.gis.geos import Point
from django.test import TestCase

# Create your tests here.
from .models import ZentraDevice
from .models import ZentraReading
from .tasks import prepareZentra
from .tasks import prepareGEFS
from .models import NoaaForecast

from django.test import TestCase


class WeatherImportTests(TestCase):
    def test_fetch_from_zentra(self):
        # Check that the prepareZentra task can run and adds some records to the db
        sn = "06-02047"
        zentraDevice = ZentraDevice(sn, location=Point(0, 0))
        zentraDevice.save()

        prepareZentra()

        # Check that there are readings in the database
        readings = ZentraReading.objects.all()
        assert len(readings) > 100

        # Check that they all relate to our device
        for reading in readings:
            assert reading.device == zentraDevice

    def test_fetch_from_GEFS(self):
        # Check that the prepareGEFS task can run and adds some records to the db
        prepareGEFS()

        # Check that there are readings in the database
        readings = NoaaForecast.objects.all()
        assert len(readings) == 64
