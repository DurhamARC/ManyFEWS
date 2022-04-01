from datetime import timedelta
from celery import Celery, shared_task
from django.conf import settings
from django.db.models import Count, Max
from django.utils import timezone
import numpy as np

from .models import (
    DepthPrediction,
    FloodModelParameters,
    ModelVersion,
    PercentageFloodRisk,
    RiverFlowCalculationOutput,
)


def run_all_flood_models():
    # Run flood model over latest outputs from river flow

    # First find latest prediction to run model
    date_aggregation = RiverFlowCalculationOutput.objects.aggregate(
        Max("prediction_date")
    )
    latest_prediction_date = date_aggregation["prediction_date__max"]

    # Next find all calculations with that date
    outputs_by_time = RiverFlowCalculationOutput.objects.filter(
        prediction_date=latest_prediction_date,
        forecast_time__lte=latest_prediction_date + timedelta(days=16),
    )
    for output in outputs_by_time:
        run_flood_model_for_time.delay(latest_prediction_date, output.forecast_time)


@shared_task(name="Run flood model for time")
def run_flood_model_for_time(prediction_date, forecast_time):
    print(f"Running flood model for {forecast_time}")
    output = RiverFlowCalculationOutput.objects.filter(
        prediction_date=prediction_date, forecast_time=forecast_time
    ).first()
    flow_values_iter = output.riverflowprediction_set.values_list(
        "river_flow", flat=True
    )
    flow_values = np.fromiter(flow_values_iter, np.dtype("float_"))
    print(f"Got river flow values: {flow_values}")

    latest_model_id = ModelVersion.get_current_id()
    params = FloodModelParameters.objects.filter(model_version_id=latest_model_id).all()

    batch_size = 1000
    i = 0

    while i < len(params):
        end = min(i + batch_size, len(params))
        param_ids = [p.id for p in params[i:end]]
        predict_depths.delay(forecast_time, param_ids, flow_values)
        i += batch_size


@shared_task(name="Predict depths for batch of cells")
def predict_depths(forecast_time, param_ids, flow_values):
    for param_id in param_ids:
        param = FloodModelParameters.objects.get(id=param_id)
        (
            lower_centile,
            mid_lower_centile,
            median,
            upper_centile,
        ) = predict_aggregated_depth(flow_values, param)

        # Replace current object if there is one
        prediction = DepthPrediction.objects.filter(
            date=forecast_time, bounding_box=param.bounding_box
        ).first()

        if not prediction:
            prediction = DepthPrediction(
                date=forecast_time, bounding_box=param.bounding_box
            )

        prediction.model_version = param.model_version
        prediction.median_depth = median
        prediction.lower_centile = lower_centile
        prediction.mid_lower_centile = mid_lower_centile
        prediction.upper_centile = upper_centile
        prediction.save()


def predict_aggregated_depth(flow_values, param):
    beta_values = [getattr(param, f"beta{i}") for i in range(12)]
    beta_values = [b for b in beta_values if b is not None]

    f = lambda x: predict_single_depth(x, beta_values)
    if len(flow_values.shape) == 1:
        # single array - apply to each
        fv = np.vectorize(f)
        depths = fv(flow_values)
    else:
        depths = np.apply_along_axis(f, -1, flow_values)

    # Get median and centiles
    median = np.median(depths)
    lower_centile = np.percentile(depths, 10)
    mid_lower_centile = np.percentile(depths, 30)
    upper_centile = np.percentile(depths, 90)

    return lower_centile, mid_lower_centile, median, upper_centile


def predict_single_depth(flows, params):
    """Expects an iterable of flow values (multiple inflows, same prediction) and an array of parameters.
    params should have one more item than flows."""
    val = params[0]
    try:
        for i in range(len(flows)):
            val += flows[i] * params[i + 1]
    except TypeError:  # flows may just be single val
        val += flows + params[1]

    return val


@shared_task(name="aggregate_flood_models")
def aggregate_flood_models_for_time(forecast_time):
    print(f"Aggregating results at time {forecast_time}")


def calculate_risk_percentages(from_date):
    # Convert aggregated depths to % risk based on number of cells
    # with non-zero median depth
    prediction_counts = (
        DepthPrediction.objects.filter(
            date__gte=from_date,
            median_depth__gte=0,
        )
        .values("date")
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
        PercentageFloodRisk.objects.filter(date=p["date"]).delete()
        PercentageFloodRisk(date=p["date"], risk=risk).save()
