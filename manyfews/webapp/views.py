from django.contrib.gis.geos import Point, Polygon
from django.http import HttpResponse, JsonResponse
from django.template import loader

from calculations.models import AggregatedDepthPrediction


def index(request):
    template = loader.get_template("webapp/index.html")
    return HttpResponse(template.render({}, request))


def depth_predictions(request, day, bounding_box):
    # TODO: get latest values not all
    predictions = AggregatedDepthPrediction.objects.filter(
        bounding_box__intersects=bounding_box
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
