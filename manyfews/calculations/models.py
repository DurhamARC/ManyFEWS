from django.contrib.gis.db import models
from django.contrib.gis.geos import Point, Polygon


class ZentraDevice(models.Model):
    device_sn = models.CharField(primary_key=True, max_length=100)
    device_name = models.CharField(max_length=100, blank=True, default="")
    location = models.PointField()
    height = models.FloatField(default=1)


class ZentraReading(models.Model):
    date = models.DateTimeField()
    device = models.ForeignKey(ZentraDevice, on_delete=models.CASCADE)
    relative_humidity = models.FloatField(null=True)
    precipitation = models.FloatField(null=True)
    air_temperature = models.FloatField(null=True)
    wind_speed = models.FloatField(null=True)
    wind_direction = models.FloatField(null=True)


class WeatherReading(models.Model):
    date = models.DateTimeField()
    location = models.PointField(default=Point(0, 0))
    precipitation = models.FloatField()
    min_temperature = models.FloatField()
    max_temperature = models.FloatField()
    wind_u = models.FloatField()
    wind_v = models.FloatField()
    relative_humidity = models.FloatField(default=0)

    class Meta:
        abstract = True


class NoaaForecast(WeatherReading):
    pass


class AggregatedZentraReading(WeatherReading):
    pass


class InitialCondition(models.Model):
    date = models.DateTimeField()
    location = models.PointField(default=Point(0, 0))
    storage_level = models.FloatField()
    slow_flow_rate = models.FloatField()
    fast_flow_rate = models.FloatField()


class RiverFlowCalculationOutput(models.Model):
    prediction_date = models.DateTimeField()
    forecast_time = models.DateTimeField()
    location = models.PointField(default=Point(0, 0))
    rain_fall = models.FloatField()
    potential_evapotranspiration = models.FloatField()


class RiverFlowPrediction(models.Model):
    prediction_index = models.IntegerField(default=int(0))
    calculation_output = models.ForeignKey(
        RiverFlowCalculationOutput, on_delete=models.CASCADE
    )
    river_flow = models.FloatField()


class AggregatedDepthPrediction(models.Model):
    prediction_date = models.DateTimeField()
    bounding_box = models.PolygonField(default=Polygon.from_bbox((0, 0, 1, 1)))
    median_depth = models.FloatField()
    lower_centile = models.FloatField()
    upper_centile = models.FloatField()
