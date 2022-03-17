from datetime import date, timedelta
import random

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.utils import timezone

from calculations.models import AggregatedDepthPrediction


def index(request):
    template = loader.get_template("webapp/index.html")
    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    daily_risks = []
    risk = random.randint(0, 100)
    for i in range(10):
        six_hour_risks = []
        for j in range(4):
            risk += random.randint(-10, 10)
            if risk < 0:
                risk = 0
            if risk > 100:
                risk = 100
            risk_level = 0
            if risk > 75:
                risk_level = 4
            elif risk > 50:
                risk_level = 3
            elif risk > 25:
                risk_level = 2
            elif risk > 0:
                risk_level = 1

            six_hour_risks.append(
                {"hour": j * 6, "risk_percentage": risk, "risk_level": risk_level}
            )

        daily_risks.append(
            {
                "day_number": i,
                "date": today + timedelta(days=i),
                "risks": six_hour_risks,
            }
        )

    return HttpResponse(
        template.render(
            {"daily_risks": daily_risks, "mapApiKey": settings.MAP_API_TOKEN}, request
        )
    )


def depth_predictions(request, day, hour, bounding_box):
    # Get the depth predictions for this bounding box and day days ahead
    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    predictions = AggregatedDepthPrediction.objects.filter(
        prediction_date=today + timedelta(days=day),
        bounding_box__intersects=bounding_box,
    )
    items = []
    for p in predictions:
        bb_extent = p.bounding_box.extent
        items.append(
            {
                "bounds": [[bb_extent[0], bb_extent[1]], [bb_extent[2], bb_extent[3]]],
                "depth": p.median_depth,
                "lower_centile": p.lower_centile,
                "upper_centile": p.upper_centile,
            }
        )
    return JsonResponse({"items": items, "max_depth": 1})
