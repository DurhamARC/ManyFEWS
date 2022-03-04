from django.contrib.gis.db import models
from django.contrib.gis.geos import Point


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
    location = models.PointField(default=Point(0, 0))
    precipitation = models.FloatField()
    min_temperature = models.FloatField()
    max_temperature = models.FloatField()
    wind_u = models.FloatField()
    wind_v = models.FloatField()
    relative_humidity = models.FloatField(default=0)


class InitialCondition(models.Model):
    date = models.DateTimeField()
    location = models.PointField(default=Point(0, 0))
    storage_level = models.FloatField()
    slow_flow_rate = models.FloatField()
    fast_flow_rate = models.FloatField()


class RainAndEvapotranspiration(models.Model):
    date = models.DateTimeField()
    location = models.PointField(default=Point(0, 0))
    rain_fall = models.FloatField()
    potential_evapotranspiration = models.FloatField()


class PotentialRiverFlows(models.Model):
    date = models.DateTimeField()
    location = models.PointField(default=Point(0, 0))
    river_flows = models.FloatField()
