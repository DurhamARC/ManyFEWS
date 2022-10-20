import csv

from celery import Celery, shared_task

from django.conf import settings
from django.contrib.gis.geos import Point, Polygon

import numpy as np
from tqdm import tqdm, trange

from webapp.models import UserAlert, UserPhoneNumber, AlertType
from zentra.api import ZentraToken

from .alerts import send_phone_alerts_for_user
from .bulk_create_manager import BulkCreateManager
from .flood_risk import run_all_flood_models, calculate_risk_percentages
from .gefs import prepareGEFS
from .generate_river_flows import (
    prepareWeatherForecastData,
    runningGenerateRiverFlows,
)
from .models import (
    AggregatedZentraReading,
    FloodModelParameters,
    InitialCondition,
    ModelVersion,
    NoaaForecast,
    ZentraDevice,
)
from .zentra import prepareZentra, offsetTime
from .zentra_devices import ZentraDeviceMap

app = Celery()

import logging

logger = logging.getLogger(__name__)


@shared_task(name="calculations.hello_celery")
def hello_celery():
    """
    This is an example of a task that can be scheduled via celery.
    """
    logger.info("Hello logging from celery!")


@shared_task(name="calculations.initialModelSetUp")
def initialModelSetUp():
    """
    Initial model set up
    This is part is only run once when the application is just installed.

    1. Start with all parameters at their default values. These are the default value that Simon passed to you.
    2. Get the last 365 days of data from the catchment via Zentra
    3. Run the model for this dataset
    4. The model will write out the initial conditions for each of the model parameter sets.
       This is the file that we will use for the next day in the processing.
    """

    backDays = settings.INITIAL_BACKTIME
    timeInfo = offsetTime(backDays=backDays)
    location = ZentraDevice.objects.get(device_sn=settings.STATION_SN).location

    # prepare the time point for getting zentra data.
    # For initial model setup, it needs 365 days zentra data.
    for backDay in trange(backDays, 0, -1):
        prepareZentra(backDay=backDay)

    # prepare weather data (from Zentra).
    weatherForecastData = prepareWeatherForecastData(
        predictionDate=timeInfo[0],
        location=location,
        dataSource="zentra",
        backDays=backDays,
    )

    # Set up an initial value for model running.
    # Here use the mean value of the reference data as its initial value,
    # Because through previous 365 days' iteration with zentra data,
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
        mode="inital",
    )


@shared_task(name="calculations.dailyModelUpdate")
def dailyModelUpdate():
    """
    On the daily updates, there are two steps that we need to do.
    1, update the model’s initial conditions based on the previous day’s weather.
    2, run the GEFS weather forecast data.

    Part 1:
    1. Get the last day’s data from Zentra
    2. Read in the initial conditions from the previous day
    3. Run the catchment model for one day with the new data
    4. Write the new initial conditions for today.
    Part 2
    1. Put together all of the time series from GEFS – there are 21 in total.
    2. Run the model with the new initial conditions (from step 4 directly above) for each of the weather
       forecast time series from step one above
    3. We now have a set of ca. 2100 time series of river flow forecast for the next 16 days.

    """

    ## Part 1
    # prepare time and location info
    location = ZentraDevice.objects.get(device_sn=settings.STATION_SN).location
    yday = offsetTime(backDays=1)
    today = offsetTime(backDays=0)

    # Check whether zentra data has been downloaded
    aggregateDataLength = len(
        AggregatedZentraReading.objects.filter(date__range=(yday[0], yday[1])).filter(
            location=location
        )
    )

    logger.info(
        """
        ZentraDevice location: {}
        Yesterday: {:%B %d, %Y}
        Today: {:%B %d, %Y}
        Zentra data records: {}
    """.format(
            location, yday[0], today[0], aggregateDataLength
        )
    )

    if aggregateDataLength == 0:
        # Get the last day’s data from Zentra
        prepareZentra(backDay=1)

    ydayZentra = prepareWeatherForecastData(
        predictionDate=yday[0], location=location, dataSource="zentra", backDays=1
    )

    # Read in the initial conditions from the previous day
    initialConditions = InitialCondition.objects.filter(date=today[0]).filter(
        location=location
    )

    # Check data input is correct
    logger.debug(
        f"InitialCondition records found: {len(initialConditions)} for location {location}"
    )
    if len(initialConditions) == 0:
        raise Exception(
            "No Initial Conditions for River Flow Prediction found for previous day! "
            "Try running calculations.initialModelSetUp first."
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
        weatherForecast=ydayZentra,
        initialData=F0,
        riverFlowSave=False,
        initialDataSave=False,
        mode="daily",
    )

    ## part 2
    # Put together all of the time series from GEFS
    gefsData = NoaaForecast.objects.filter(date__range=(today[0], today[1]))

    if len(gefsData) == 0:
        # Check whether GEFS data has been downloaded
        prepareGEFS()

    weatherForecastData = prepareWeatherForecastData(
        predictionDate=today[0], location=location, dataSource="gefs"
    )

    # Run the model with the new initial conditions
    runningGenerateRiverFlows(
        predictionDate=today[0],
        dataLocation=location,
        weatherForecast=weatherForecastData,
        initialData=updateInitialData,
        riverFlowSave=True,
        initialDataSave=True,
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


@shared_task(name="Load parameters")
def load_params_from_csv(filename, model_version_id):
    logger.info(f"Loading parameters from {filename}")

    total_rows = sum(1 for _ in open(filename))
    logger.info(
        f"CSV file contains {total_rows} rows. Loading in chunks of {settings.DATABASE_CHUNK_SIZE}..."
    )

    with open(filename) as csvfile:
        bulk_mgr = BulkCreateManager(chunk_size=settings.DATABASE_CHUNK_SIZE)

        for row in tqdm(csv.DictReader(csvfile), total=total_rows, mininterval=5):
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


@shared_task(name="Import Zentra Devices")
def import_zentra_devices():
    token = ZentraToken(username=settings.ZENTRA_UN, password=settings.ZENTRA_PW)
    device_map = ZentraDeviceMap(token=token)
    device_map.save()
