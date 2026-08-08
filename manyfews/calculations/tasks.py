import csv

from celery import shared_task

from django.conf import settings
from django.contrib.gis.geos import Point, Polygon

import numpy as np
from tqdm import tqdm

from webapp.models import UserAlert, UserPhoneNumber, AlertType

from .alerts import send_phone_alerts_for_user
from .bulk_create_manager import BulkCreateManager
from .flood_risk import run_all_flood_models, calculate_risk_percentages
from .generate_river_flows import (
    prepareWeatherForecastData,
    runningGenerateRiverFlows,
)
from .models import (
    AggregatedWeatherReading,
    FloodModelParameters,
    InitialCondition,
    ModelVersion,
    NoaaForecast,
    PercentageFloodRisk,
    AggregatedDepthPrediction,
    DepthPrediction,
    RiverFlowPrediction,
    RiverFlowCalculationOutput,
)
from .open_meteo import prepareOpenMeteo, prepareOpenMeteoHistorical, offsetTime

from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(name="calculations.hello_celery")
def hello_celery():
    """
    This is an example of a task that can be scheduled via celery.
    """
    logger.info("Hello logging from celery!")


@shared_task(name="calculations.initialModelSetUp", bind=True)
def initialModelSetUp(self):
    """
    Initial model set up
    This is part is run once when the application is just installed.
    It must be run again if the scheduled tasks were not run in the last INITIAL_BACKTIME days.

    1. Start with all parameters at their default values.
    2. Get the last INITIAL_BACKTIME days of historical weather for the catchment from Open-Meteo
    3. Run the model for this dataset
    4. The model will write out the initial conditions for each of the model parameter sets.
       This is the file that we will use for the next day in the processing.
    """

    backDays = settings.INITIAL_BACKTIME
    timeInfo = offsetTime(backDays=backDays)
    location = Point(settings.LON_VALUE, settings.LAT_VALUE)

    logger.info(
        f"Setting up catchment model:\n"
        f"\tLocation: {location}\n"
        f"\tINITIAL_BACKTIME is {backDays}\n"
        f"\tStarting on {timeInfo[0].strftime('%Y-%m-%d %H:%M:%S')}"
    )

    # Get the last `backDays` days of historical weather (ending yesterday - today
    # isn't "historical" yet) from Open-Meteo's archive API in a single request.
    yesterday, _ = offsetTime(backDays=1)
    prepareOpenMeteoHistorical(start_date=timeInfo[0], end_date=yesterday)

    # prepare weather data (from Open-Meteo historical archive).
    weatherForecastData = prepareWeatherForecastData(
        predictionDate=timeInfo[0],
        location=location,
        dataSource="historical",
        backDays=backDays,
    )

    # Set up an initial value for model running.
    # Here use the mean value of the reference data as its initial value,
    # Because through previous `backDays` days' iteration with historical data,
    # it will be pulled back to the real.

    initialConditionData = np.tile((np.array([20.556992, 3.86579, 1.862992])), (100, 1))

    # run model
    runningGenerateRiverFlows(
        predictionDate=timeInfo[0],
        dataLocation=location,
        weatherForecast=weatherForecastData,
        initialData=initialConditionData,
        riverFlowSave=False,
        initialDataSave=True,
        mode="initial",
    )


@shared_task(name="calculations.dailyModelUpdate")
def dailyModelUpdate():
    """
    On the daily updates, there are two steps that we need to do.
    1, update the model’s initial conditions based on the previous day’s weather.
    2, run the Open-Meteo ensemble weather forecast data.

    Part 1:
    1. Get the last day’s historical weather from Open-Meteo
    2. Read in the initial conditions from the previous day
    3. Run the catchment model for one day with the new data
    4. Write the new initial conditions for today.
    Part 2
    1. Fetch the Open-Meteo ensemble forecast - every ensemble member's weather trajectory.
    2. Run the model with the new initial conditions (from step 4 directly above) for each
       ensemble member's forecast time series from step one above.
    3. We now have a set of river flow forecasts for the next OPEN_METEO_FORECAST_DAYS days,
       for every ensemble member - flood_risk.py combines these with the 100 parameter-set
       realisations to get depth-prediction uncertainty bounds that reflect both parameter
       and weather-forecast uncertainty.

    """

    ## Part 1
    # prepare time and location info
    location = Point(settings.LON_VALUE, settings.LAT_VALUE)
    yday = offsetTime(backDays=1)
    today = offsetTime(backDays=0)

    # Check whether historical data has been downloaded for yesterday
    aggregateDataLength = len(
        AggregatedWeatherReading.objects.filter(date__range=(yday[0], yday[1])).filter(
            location=location
        )
    )

    logger.info(
        """
        Location: {}
        Yesterday: {:%B %d, %Y}
        Today: {:%B %d, %Y}
        Historical weather records: {}
    """.format(
            location, yday[0], today[0], aggregateDataLength
        )
    )

    if aggregateDataLength == 0:
        # Get the last day’s data from Open-Meteo's historical archive
        prepareOpenMeteoHistorical(start_date=yday[0], end_date=yday[0])

    ydayWeather = prepareWeatherForecastData(
        predictionDate=yday[0], location=location, dataSource="historical", backDays=1
    )

    # Read in the initial conditions from the previous day
    initialConditions = InitialCondition.objects.filter(date=today[0]).filter(
        location=location
    )

    if len(initialConditions) == 0:
        logger.error(
            "No Initial Conditions for River Flow Prediction found for previous day! "
            "Will now run calculations.initialModelSetUp"
        )

        # Run calculations.initialModelSetUp to get initial conditions
        initialModelSetUp()
        initialConditions = InitialCondition.objects.filter(date=today[0]).filter(
            location=location
        )

    # Check data input is correct
    logger.debug(
        f"InitialCondition records found: {len(initialConditions)} for location {location}"
    )

    slowFlowRateList = []
    fastFlowRateList = []
    storageLevelList = []

    # extract output initial condition of river flows model.
    for data in initialConditions:
        slowFlowRateList.append(data.slow_flow_rate)
        fastFlowRateList.append(data.fast_flow_rate)
        storageLevelList.append(data.storage_level)

    initialConditionsList = list(
        zip(storageLevelList, slowFlowRateList, fastFlowRateList)
    )
    F0 = np.array(initialConditionsList)

    # Run the model for one day with the new data
    updateInitialData = runningGenerateRiverFlows(
        predictionDate=today[0],
        dataLocation=location,
        weatherForecast=ydayWeather,
        initialData=F0,
        riverFlowSave=False,
        initialDataSave=False,
        mode="daily",
    )

    ## part 2
    # Fetch the Open-Meteo ensemble forecast if not already downloaded for today
    todaysForecast = NoaaForecast.objects.filter(issue_date__range=(today[0], today[1]))

    if len(todaysForecast) == 0:
        logger.info("Preparing Open-Meteo ensemble forecast data")
        prepareOpenMeteo()
        todaysForecast = NoaaForecast.objects.filter(
            issue_date__range=(today[0], today[1])
        )

    members = list(
        todaysForecast.order_by("ensemble_member")
        .values_list("ensemble_member", flat=True)
        .distinct()
    )
    if not members:
        raise RuntimeError(
            "No Open-Meteo forecast data found for today - check prepareOpenMeteo() ran successfully."
        )

    # The "control" (deterministic) member drives tomorrow's saved initial
    # conditions, so state carry-forward stays unambiguous across ensemble
    # members. Every member's flood forecast still gets saved (riverFlowSave),
    # so flood_risk.py can combine all members' river flows to reflect
    # weather-forecast uncertainty alongside the existing 100-parameter-set
    # uncertainty.
    control_member = "control" if "control" in members else members[0]
    logger.info(f"Running river flow model for {len(members)} ensemble members")

    for member in members:
        memberForecastData = prepareWeatherForecastData(
            predictionDate=today[0],
            location=location,
            dataSource="forecast",
            ensemble_member=member,
        )

        # Run the catchment model with the new initial conditions. Each member
        # needs its own independent copy of updateInitialData: ModelFun
        # mutates F0 in place, so sharing the array across members would let
        # one member's run pollute the starting state for the next.
        runningGenerateRiverFlows(
            predictionDate=today[0],
            dataLocation=location,
            weatherForecast=memberForecastData,
            initialData=updateInitialData.copy(),
            riverFlowSave=True,
            initialDataSave=(member == control_member),
            mode="daily",
        )


@shared_task(name="Run flood model")
def run_flood_model():
    run_all_flood_models()


@shared_task(name="Calculate percentage risks")
def calculate_percentage_risk():
    calculate_risk_percentages()


@shared_task(name="Send user SMS alerts")
def send_user_sms_alerts(user_id, phone_number_id):
    send_phone_alerts_for_user(user_id, phone_number_id, alert_type=AlertType.SMS)


@shared_task(name="Send all alerts")
def send_alerts():
    # Get and send SMS alerts
    # Group by user and phone number, so we can send alerts for multiple locations at once
    sms_alerts = (
        UserAlert.objects.filter(verified=True, alert_type=AlertType.SMS)
        .values("user_id", "phone_number")
        .distinct()
    )
    for alert_details in sms_alerts:
        result = send_user_sms_alerts.delay(
            alert_details["user_id"], alert_details["phone_number"]
        )


@shared_task(name="Load parameters", bind=True)
def load_params_from_csv(self, filename: str, model_version_id: str):
    logger.info(f"Loading parameters from {filename}")

    total_rows = sum(1 for _ in open(filename, encoding="utf-8-sig"))
    logger.info(
        f"CSV file contains {total_rows} rows. Loading in chunks of {settings.DATABASE_CHUNK_SIZE}..."
    )

    with open(filename, mode="r", encoding="utf-8-sig") as csvfile:
        bulk_mgr = BulkCreateManager(chunk_size=settings.DATABASE_CHUNK_SIZE)

        for row in tqdm(
            csv.DictReader(csvfile), desc=self.name, total=total_rows, mininterval=5
        ):
            if row["size"] == "":
                continue

            size_to_add = float(row["size"]) / 2
            x = float(row["lng"])
            y = float(row["lat"])

            # Remove already used values from row data
            for i in ("lng", "lat", "size"):  # Use tuple O(1)
                row.pop(i)

            # Only save param if it has at least 1 non-zero beta value
            columns = len(row)
            if columns > 0:
                # Check that the CSV file row isn't longer than we can insert into Model:
                if columns > 12:
                    raise Exception(
                        "More rows in the input CSV than columns in FloodModelParameters Model!"
                    )

                # Construct model object and add to database insert list
                bulk_mgr.add(
                    FloodModelParameters(
                        model_version_id=model_version_id,
                        bounding_box=Polygon.from_bbox(
                            (
                                x - size_to_add,
                                y - size_to_add,
                                x + size_to_add,
                                y + size_to_add,
                            )
                        ),
                        # Insert other columns from CSV into betaXX parameters in Model using variable expansion:
                        **{
                            f"beta{current}": float(row[key])
                            for current, key in enumerate(row)
                        },
                    )
                )

        bulk_mgr.done()

    logger.info("Saved model parameters.")

    # Clean up old parameters from db
    current_model_version_id = ModelVersion.get_current_id()
    FloodModelParameters.objects.exclude(
        model_version_id=current_model_version_id, depthprediction=None
    ).delete()
    logger.info("Deleted old model parameters")


@shared_task(name="calculations.dropCalculatedValues")
def drop_database():
    logger.info("Dropping all calculated values")

    PercentageFloodRisk.objects.all().delete()
    AggregatedDepthPrediction.objects.all().delete()
    DepthPrediction.objects.all().delete()
    RiverFlowPrediction.objects.all().delete()
    RiverFlowCalculationOutput.objects.all().delete()
    InitialCondition.objects.all().delete()
    AggregatedWeatherReading.objects.all().delete()
    NoaaForecast.objects.all().delete()
