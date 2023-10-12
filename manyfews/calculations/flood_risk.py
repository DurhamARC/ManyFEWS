from datetime import timedelta
import math
import time

from celery import shared_task
from django.conf import settings
from django.contrib.gis.db.models import Extent
from django.contrib.gis.geos import Polygon
from django.db.models import Avg, Count, Max
from django.utils import timezone
import numpy as np
from numba import jit

from .bulk_create_manager import BulkCreateUpdateManager
from .models import (
    AggregatedDepthPrediction,
    DepthPrediction,
    FloodModelParameters,
    ModelVersion,
    PercentageFloodRisk,
    RiverFlowCalculationOutput,
    RiverChannel,
)

from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

# Generate list of [beta0..beta4]
BETA_ARGS = [f"beta{i}" for i in range(5)]


def run_all_flood_models():
    # Run flood model over latest outputs from river flow

    # First find latest prediction to run model
    date_aggregation = RiverFlowCalculationOutput.objects.aggregate(
        Max("prediction_date")
    )
    latest_prediction_date = date_aggregation["prediction_date__max"]

    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Next find all calculations with that date, in the next 16 days
    outputs_by_time = RiverFlowCalculationOutput.objects.filter(
        prediction_date=latest_prediction_date,
        forecast_time__lte=today + timedelta(days=16),
    )
    # Raise an error and stop the program if outputs_by_time is empty
    if len(outputs_by_time) == 0:
        raise RuntimeError(
            "No River Flow result found. Check the task dailyModelUpdate ran properly."
        )

    logger.info(f"Found {len(outputs_by_time)} sets of output data.")
    for output in outputs_by_time:
        run_flood_model_for_time.delay(latest_prediction_date, output.forecast_time)


@shared_task(name="Run flood model for time")
def run_flood_model_for_time(prediction_date, forecast_time):
    logger.info(f"Running flood model for {forecast_time}")
    output = RiverFlowCalculationOutput.objects.filter(
        prediction_date=prediction_date, forecast_time=forecast_time
    ).first()
    flow_values_iter = output.riverflowprediction_set.values_list(
        "river_flow", flat=True
    )
    flow_values = np.fromiter(flow_values_iter, np.dtype("float_"))
    logger.info(
        f"Got river flow values: "
        f"[{', '.join(format(x, '2.5f') for x in flow_values[:2])} ... "
        f"{', '.join(format(x, '2.5f') for x in flow_values[-2:])}]."
    )

    latest_model_id = ModelVersion.get_current_id()
    params = FloodModelParameters.objects.filter(model_version_id=latest_model_id)

    # Check if we have FloodModel parameters (common error in app setup)
    if not len(params):
        raise RuntimeError(
            "There are no FloodModelParameters populated"
            f" for {prediction_date.strftime('%Y-%m-%d')} {forecast_time.strftime('%H:%M:%S')}"
            " and therefore nothing to do."
            "\nHave you added a ModelVersion? You may need to load the model parameters from CSV."
        )

    # Perform check: will depth be zero for all cells? beta4 is minQ. Early-out if so.
    elif max(flow_values) < min(params.only("beta4").values_list("beta4", flat=True)):
        logger.warning(
            "No floods (flow_rate < minQ).\n"
            "Maximum predicted river flow rate"
            f" for {prediction_date.strftime('%Y-%m-%d')} {forecast_time.strftime('%H:%M:%S')}"
            " is less than (<) minimum minQ in the flood model parameters.\n"
            "Depth would be 0 for every cell. All existing predictions for this date/time will be removed."
        )

        DepthPrediction.objects.filter(
            date=forecast_time, parameters_id__in=params
        ).delete()

        return

    # FIXME: this is slow (both with celery in batches of 1000, and running in series
    # (took several hours for 1 time))
    predict_depths(forecast_time, [p.id for p in params.only("id").all()], flow_values)

    # count the total number of processed pixels.
    total_pixel_count = DepthPrediction.objects.count()
    logger.info(f"Total Depth Predictions made: {total_pixel_count}")

    if total_pixel_count == 0:
        raise RuntimeError(
            "There are no floods that occurred, or check the parameter file."
        )
    else:
        aggregate_flood_models(forecast_time)

    # TODO: join results to call aggregate_flood_models


@shared_task(name="Predict depths")
def predict_depths(forecast_time, param_ids, flow_values):
    bulk_mgr = BulkCreateUpdateManager(
        chunk_size=settings.DATABASE_CHUNK_SIZE,
        fields=(
            "model_version",
            "median_depth",
            "lower_centile",
            "mid_lower_centile",
            "upper_centile",
        ),
    )

    channels = RiverChannel.objects.all()
    if not channels:
        logger.warning("No river channels found")

    predictions_to_delete = []
    batch_size = settings.DATABASE_CHUNK_SIZE
    total_batches = int(math.ceil(len(param_ids) / batch_size))

    for batch in range(total_batches):
        start = time.time()

        params_batch = FloodModelParameters.objects.defer("bounding_box").filter(
            id__in=param_ids
        )[batch * batch_size : (batch + 1) * batch_size]

        # Preload existing predictions for batch and insert into dictionary by parameters_id
        # Do a single database SELECT query for batch instead of making a SELECT query
        #   for each pixel (by default up to 1,000 records)
        # Note that if the Flood Model has not run, this will return with len() == 0!
        existing_predictions = {
            rec.parameters_id: rec
            for rec in DepthPrediction.objects.filter(
                date=forecast_time, parameters_id__in=params_batch
            )
            .only("parameters_id")
            .all()
        }

        for i, param in enumerate(params_batch):
            prediction = None
            if param.id in existing_predictions:
                prediction = existing_predictions[param.id]

            process_pixel(
                param,
                flow_values,
                channels,
                forecast_time,
                predictions_to_delete,
                bulk_mgr,
                prediction,
            )

        # Clean up cell depth predictions to delete once per patch
        if len(predictions_to_delete) > settings.DATABASE_CHUNK_SIZE:
            logger.debug(
                f"Cleaning up {len(predictions_to_delete)} no-longer flooded cells"
            )
            DepthPrediction.objects.filter(pk__in=predictions_to_delete).delete()
            predictions_to_delete = []

        end = time.time()

        logger.info(
            f"Calculated {(batch+1) * batch_size} of {total_batches * batch_size} pixels "
            f"in batch {batch+1}/{total_batches} ({(batch / total_batches) * 100 :.1f}%) "
            f"for {forecast_time.strftime('%y-%m-%d %H:%M')}. Executed in {(end-start):.2f}s"
        )

    if len(predictions_to_delete):
        logger.debug(
            f"Cleaning up {len(predictions_to_delete)} remaining no-longer flooded cells"
        )
        DepthPrediction.objects.filter(pk__in=predictions_to_delete).delete()

    bulk_mgr.done()


def process_pixel(
    param,
    flow_values,
    channels,
    forecast_time,
    predictions_to_delete,
    bulk_mgr,
    prediction,
):

    # Break out of loop if current param is within a river channel
    # (there may be more than one river channel returned)
    for channel in channels:
        # Check if param is within RiverChannel
        if channel.channel_location.intersects(param.bounding_box):
            return

    (
        lower_centile,
        mid_lower_centile,
        median,
        upper_centile,
    ) = predict_depth(flow_values, param)

    # Replace current object if there is one
    if upper_centile <= 0:
        if prediction:
            predictions_to_delete.append(prediction.pk)

    else:
        new_prediction = DepthPrediction(
            date=forecast_time,
            parameters_id=param.id,
            model_version=param.model_version,
            median_depth=median,
            lower_centile=lower_centile,
            mid_lower_centile=mid_lower_centile,
            upper_centile=upper_centile,
        )

        if prediction:  # update:
            new_prediction.pk = prediction.pk
            bulk_mgr.update(new_prediction)

        else:  # create:
            bulk_mgr.add(new_prediction)


@jit(nopython=False)
def predict_depth(flow_values, param):
    """
    Predict the depth of a cell using numpy polynomial
    @param flow_values:
    @param param:
    @return:
    """

    # FIXME: getattr is slow
    beta_values = [getattr(param, i, 0) for i in BETA_ARGS]
    beta_values = [0 if b is None else b for b in beta_values]

    minQ = beta_values[4]
    beta_values = beta_values[:4]

    depths = np.zeros_like(flow_values)
    for index, element in np.ndenumerate(flow_values):
        # minQ is the minimum flow rate to calculate polynomial on
        # If we're less than the minimum flow rate, then depth = 0
        if element < minQ:
            depth = 0
        else:
            polynomial = np.polynomial.Polynomial(beta_values)
            depth = polynomial(element)

        depths[index] = depth

    # TODO: Does this have any effect?
    depths[depths < 0] = 0

    # Get median and centiles
    median = np.median(depths)
    lower_centile = np.percentile(depths, 10)
    mid_lower_centile = np.percentile(depths, 30)
    upper_centile = np.percentile(depths, 90)

    # logger.debug(
    #    f"depths type {type(depths)}, shape: {np.shape(depths)}"
    # )
    # logger.debug(
    #    f"get median and centiles: {median} & {mid_lower_centile} & {upper_centile}"
    # )

    return lower_centile, mid_lower_centile, median, upper_centile


@shared_task(name="aggregate_flood_models")
def aggregate_flood_models(date):
    logger.info(f"Aggregating flood model results for responsive tiling")
    current_model_version_id = ModelVersion.get_current_id()
    result = DepthPrediction.objects.filter(
        date=date, model_version_id=current_model_version_id
    ).aggregate(Extent("parameters__bounding_box"))

    extent = result["parameters__bounding_box__extent"]

    if extent is None:
        raise Exception(
            "Extent is None – no bounding box defined in Flood Model Parameters!"
        )

    for i in [32, 64, 128, 256]:
        aggregate_flood_models_by_size.delay(date, current_model_version_id, extent, i)


@shared_task(name="aggregate_flood_models_by_size")
def aggregate_flood_models_by_size(date, model_version_id, extent, i):
    logger.info(f"Aggregating for date {date} level {i}")
    bulk_mgr = BulkCreateUpdateManager(
        chunk_size=settings.DATABASE_CHUNK_SIZE,
        fields=(
            "model_version_id",
            "median_depth",
            "lower_centile",
            "mid_lower_centile",
            "upper_centile",
            "aggregation_level",
        ),
    )

    total_width = extent[2] - extent[0]
    total_height = extent[3] - extent[1]
    block_size = min(total_height, total_width) / i

    x = extent[0]
    y = extent[1]

    while y < extent[3]:
        while x < extent[2]:
            x_max = x + block_size
            y_max = y + block_size
            new_bb = Polygon.from_bbox((x, y, x_max, y_max))

            q = DepthPrediction.objects.filter(
                date=date,
                parameters__bounding_box__within=new_bb,
                model_version_id=model_version_id,
            )
            values = q.aggregate(
                Avg("median_depth"),
                Avg("lower_centile"),
                Avg("mid_lower_centile"),
                Avg("upper_centile"),
            )

            if values["median_depth__avg"]:
                agg = AggregatedDepthPrediction.objects.filter(
                    date=date, bounding_box=new_bb
                ).first()

                if not agg:
                    bulk_mgr.add(
                        AggregatedDepthPrediction(
                            date=date,
                            bounding_box=new_bb,
                            model_version_id=model_version_id,
                            median_depth=values["median_depth__avg"],
                            lower_centile=values["lower_centile__avg"],
                            mid_lower_centile=values["mid_lower_centile__avg"],
                            upper_centile=values["upper_centile__avg"],
                            aggregation_level=i,
                        )
                    )
                else:
                    agg.model_version_id = model_version_id
                    agg.median_depth = values["median_depth__avg"]
                    agg.lower_centile = values["lower_centile__avg"]
                    agg.mid_lower_centile = values["mid_lower_centile__avg"]
                    agg.upper_centile = values["upper_centile__avg"]
                    agg.aggregation_level = i
                    bulk_mgr.update(agg)

            x += block_size

        x = extent[0]
        y += block_size

    bulk_mgr.done()


@shared_task(name="calculate_risk_percentages")
def calculate_risk_percentages():
    # Convert aggregated depths to % risk based on number of cells
    # with non-zero median depth
    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    prediction_counts = (
        DepthPrediction.objects.filter(
            date__gte=today,
            median_depth__gt=0,
        )
        .values("date")
        .annotate(non_zero_count=Count("median_depth"))
        .all()
    )

    logger.info("Prediction counts total: {}".format(len(prediction_counts)))

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
