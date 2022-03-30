from django.conf import settings
from django.db.models import Count

from .models import AggregatedDepthPrediction, PercentageFloodRisk


def calculate_risk_percentages(from_date):
    # Convert aggregated depths to % risk based on number of cells
    # with non-zero median depth
    prediction_counts = (
        AggregatedDepthPrediction.objects.filter(
            prediction_date__gte=from_date, median_depth__gte=0,
        )
        .values("prediction_date")
        .annotate(non_zero_count=Count("median_depth"))
        .all()
    )

    for p in prediction_counts:
        n = p["non_zero_count"]
        risk = 0
        # No risk if number of cells with 'flood' is less than number of cells
        # that are in the river channel
        if n < settings.CHANNEL_CELL_COUNT:
            risk = 0
        elif n > settings.LARGE_FLOOD_COUNT:
            risk = 1
        else:
            risk = n / (settings.LARGE_FLOOD_COUNT - settings.CHANNEL_CELL_COUNT)

        # Delete existing row for this date before creating new
        PercentageFloodRisk.objects.filter(
            prediction_date=p["prediction_date"]
        ).delete()
        PercentageFloodRisk(prediction_date=p["prediction_date"], risk=risk).save()
