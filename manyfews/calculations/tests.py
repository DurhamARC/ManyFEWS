from django.test import TestCase

# Create your tests here.
from .models import ZentraDevice
from .models import ZentraReading
from .tasks import prepareZentra

from django.test import TestCase


class WeatherImportTests(TestCase):
    def test_fetch_from_zentra(self):

        # set up the info of Zentra Device for testing purpose.
        zentraDevice = ZentraDevice("06-02047", location=Point(0, 0))
        zentraDevice.save()

        prepareZentra()


#        readings = ZentraReading.objects.all()
#        assert len(readings) > 0
