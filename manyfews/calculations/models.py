from django.db.models import Max
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point, Polygon


class ModelVersion(models.Model):
    version_name = models.CharField(max_length=50)
    date_created = models.DateTimeField(auto_now_add=True)
    is_current = models.BooleanField()
    param_file = models.FileField(upload_to="params/")

    __original_param_file = None
    __original_is_current = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_param_file = self.param_file
        self.__original_is_current = self.is_current

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.is_current:
            for version in (
                ModelVersion.objects.filter(is_current=True).exclude(id=self.id).all()
            ):
                version.is_current = False
                version.save()

        # Load params into db if is_current and either param_file or is_current has changed
        if (
            self.param_file
            and self.is_current
            and (
                self.param_file != self.__original_param_file
                or not self.__original_is_current
            )
        ):
            from .tasks import load_params_from_csv

            load_params_from_csv.delay(self.param_file.path, self.id)

    @staticmethod
    def get_current_id():
        result = ModelVersion.objects.filter(is_current=True).aggregate(Max("id"))
        return result["id__max"]


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


class FloodModelParameters(models.Model):
    model_version = models.ForeignKey(ModelVersion, on_delete=models.CASCADE)
    bounding_box = models.PolygonField(default=Polygon.from_bbox((0, 0, 1, 1)))
    beta0 = models.FloatField()
    # Allow variable number of parameters - we'll just use the populated ones
    beta1 = models.FloatField(null=True)
    beta2 = models.FloatField(null=True)
    beta3 = models.FloatField(null=True)
    beta4 = models.FloatField(null=True)
    beta5 = models.FloatField(null=True)
    beta6 = models.FloatField(null=True)
    beta7 = models.FloatField(null=True)
    beta8 = models.FloatField(null=True)
    beta9 = models.FloatField(null=True)
    beta10 = models.FloatField(null=True)
    beta11 = models.FloatField(null=True)
    beta12 = models.FloatField(null=True)


class AbstractDepthPrediction(models.Model):
    date = models.DateTimeField()
    model_version = models.ForeignKey(ModelVersion, on_delete=models.CASCADE)
    bounding_box = models.PolygonField(default=Polygon.from_bbox((0, 0, 1, 1)))
    median_depth = models.FloatField()
    # lower is 10th centile
    lower_centile = models.FloatField()
    # mid_lower is 30th centile
    mid_lower_centile = models.FloatField()
    # upper is 90th centile
    upper_centile = models.FloatField()

    class Meta:
        abstract = True


class DepthPrediction(AbstractDepthPrediction):
    pass


class AggregatedDepthPrediction(AbstractDepthPrediction):
    aggregation_level = models.IntegerField()


class PercentageFloodRisk(models.Model):
    date = models.DateTimeField()
    risk = models.FloatField()
