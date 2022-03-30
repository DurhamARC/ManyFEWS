import datetime
import random

from django.contrib.gis.geos import Point, Polygon
from django.utils import timezone

from calculations.models import ZentraDevice, AggregatedDepthPrediction

# generate some random data for test purposes
sn = "06-02047"

zentraDevice = ZentraDevice.objects.filter(device_sn=sn).first()
if not zentraDevice:
    zentraDevice = ZentraDevice(device_sn=sn, location=Point(107.735, -7.065))
    zentraDevice.save()

start_location = Point(107.735, -7.065)
date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
grid_size = 0.00001

for d in range(40):
    prediction_count = AggregatedDepthPrediction.objects.filter(
        prediction_date=date
    ).count()
    if prediction_count == 0:
        for i in range(3000):
            for j in range(3000):
                # Generate data for 1 point in 50
                if random.random() < 0.02:
                    bounding_box = Polygon.from_bbox(
                        (
                            start_location.x + grid_size * i,
                            start_location.y + grid_size * j,
                            start_location.x + grid_size * (i + 1),
                            start_location.y + grid_size * (j + 1),
                        )
                    )
                    median_depth = random.random()
                    mid_lower_centile = median_depth - random.random() * median_depth
                    prediction = AggregatedDepthPrediction(
                        prediction_date=date,
                        bounding_box=bounding_box,
                        median_depth=median_depth,
                        mid_lower_centile=mid_lower_centile,
                        lower_centile=mid_lower_centile
                        - random.random() * mid_lower_centile,
                        upper_centile=median_depth + random.random() * 0.5,
                    )
                    prediction.save()

    date += datetime.timedelta(hours=6)
