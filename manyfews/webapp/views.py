from datetime import date, timedelta
import random

from django.http import HttpResponse, JsonResponse
from django.template import loader

from calculations.models import AggregatedDepthPrediction


def index(request):
    template = loader.get_template("webapp/index.html")
    today = date.today()
    daily_risks = []
    for i in range(7):
        risk = random.randint(0, 100)
        risk_level = 0
        if risk > 75:
            risk_level = 4
        elif risk > 50:
            risk_level = 3
        elif risk > 25:
            risk_level = 2
        elif risk > 0:
            risk_level = 1

        daily_risks.append(
            {
                "day_number": i,
                "date": today + timedelta(days=i),
                "risk_percentage": risk,
                "risk_level": risk_level,
            }
        )

    return HttpResponse(template.render({"daily_risks": daily_risks}, request))


def depth_predictions(request, day, bounding_box):
    # Get the depth predictions for this bounding box and day days ahead
    predictions = AggregatedDepthPrediction.objects.filter(
        prediction_date=date.today() + timedelta(days=day),
        bounding_box__intersects=bounding_box,
    )
    items = []
    for p in predictions:
        bb_extent = p.bounding_box.extent
        items.append(
            {
                "bounds": [[bb_extent[0], bb_extent[1]], [bb_extent[2], bb_extent[3]]],
                "depth": p.median_depth,
            }
        )
    return JsonResponse({"items": items})
