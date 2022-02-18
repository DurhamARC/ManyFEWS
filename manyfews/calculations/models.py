from django.contrib.gis.db import models


class ZentraDevice(models.Model):
    device_sn = models.CharField(primary_key=True, max_length=100)
    device_name = models.CharField(max_length=100, blank=True, default="")
    location = models.PointField()
    height = models.FloatField(default=1)


class ZentraReading(models.Model):
    date = models.DateTimeField()
    device = models.ForeignKey(ZentraDevice, on_delete=models.CASCADE)
    relative_humidity = models.FloatField()
    precipitation = models.FloatField()
    air_temperature = models.FloatField()
    wind_speed = models.FloatField()
    wind_direction = models.FloatField()
    # energy?


class NoaaForecast(models.Model):
    date = models.DateTimeField()
    location = models.PointField()
    precipitation = models.FloatField()
    min_temperature = models.FloatField()
    max_temperature = models.FloatField()
    wind_u = models.FloatField()
    wind_v = models.FloatField()


# Should we convert Noaa/Zentra data to the same format before storing?
