from django.http import HttpResponse, JsonResponse
from django.template import loader

from calculations.models import AggregatedDepthPrediction


def index(request):
    template = loader.get_template("webapp/index.html")
    return HttpResponse(template.render({}, request))


def depth_predictions(request):
    # TODO: get latest values not all
    predictions = AggregatedDepthPrediction.objects.all()
    items = []
    for p in predictions:
        items.append(
            {
                "bounds": [
                    [p.lower_bound.x, p.lower_bound.y],
                    [p.upper_bound.x, p.upper_bound.y],
                ],
                "depth": p.median_depth,
            }
        )
    return JsonResponse({"items": items})
