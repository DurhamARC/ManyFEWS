import datetime
import random

from django.contrib.gis.geos import Point, Polygon
from django.utils import timezone

from calculations.models import ZentraDevice, AggregatedDepthPrediction

# generate some random data for test purposes
sn = "06-02047"

zentraDevice = ZentraDevice.objects.filter(device_sn=sn).first()
if not zentraDevice:
    zentraDevice = ZentraDevice(device_sn=sn, location=Point(-7.052115, 107.755514))
    zentraDevice.save()

start_location = Point(-7.065, 107.735)
date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
grid_size = 0.0005

for d in range(40):
    prediction_count = AggregatedDepthPrediction.objects.filter(
        prediction_date=date
    ).count()
    if prediction_count == 0:
        for i in range(100):
            for j in range(150):
                # Generate data for 1 point in 3
                if random.random() < 0.33:
                    bounding_box = Polygon.from_bbox(
                        (
                            start_location.x + grid_size * i,
                            start_location.y + grid_size * j,
                            start_location.x + grid_size * (i + 1),
                            start_location.y + grid_size * (j + 1),
                        )
                    )
                    median_depth = random.random()
                    prediction = AggregatedDepthPrediction(
                        prediction_date=date,
                        bounding_box=bounding_box,
                        median_depth=median_depth,
                        centile_25=median_depth - random.random() * median_depth,
                        centile_75=median_depth + random.random() * 0.5,
                    )
                    prediction.save()

    date += datetime.timedelta(hours=6)
