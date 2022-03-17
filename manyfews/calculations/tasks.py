from celery import Celery, shared_task
from celery.schedules import crontab
from django_celery_beat.models import CrontabSchedule, PeriodicTask
from .zentra import zentraReader, offsetTime, aggregateZentraData
from django.conf import settings
from .models import AggregatedZentraReading, InitialCondition
from .generate_river_flows import (
    prepareWeatherForecastData,
    runningGenerateRiverFlows,
    prepareInitialCondition,
)
from django.contrib.gis.geos import Point
from .zentra import prepareZentra, offsetTime
from datetime import datetime, timedelta, timezone
import os
from tqdm import trange
import numpy as np

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

    backDays = int(settings.INITIAL_BACKTIME)
    timeInfo = offsetTime(backDays=365)
    location = Point(0, 0)

    # Set up an initial value for model running.
    # Here use the mean value of the reference data as its initial value,
    # Because through previous 365 days' iteration with zentra data,
    # it will be pulled back to the real.
    referenceData = np.tile((np.array([20.556992, 3.86579, 1.862992])), (100, 1))

    # import initial data into DB ( 'calculations_initialcondition' table)
    for i in range(len(referenceData)):
        initialData = InitialCondition(
            date=timeInfo[0],
            location=location,
            storage_level=referenceData[i, 0],
            slow_flow_rate=referenceData[i, 1],
            fast_flow_rate=referenceData[i, 2],
        )
        initialData.save()

    for backDay in trange(backDays, 16, -1):

        if backDay == backDays:
            # First prepare weather data for the all next 16 days from the start time.
            for i in trange(backDays, (backDays - 16), -1):
                prepareZentra(backDay=i)

        else:
            # Then prepare the next 16 days' daily weather data.
            prepareZentra(backDay=(backDay - 15))

        # prepare start date.
        predictionData = timeInfo[0] + timedelta(days=(365 - backDay))

        # prepare data.
        weatherForecastData = prepareWeatherForecastData(
            predictionDate=predictionData, location=location, dataSource="zentra"
        )
        intialConditionData = prepareInitialCondition(
            predictionDate=predictionData, location=location
        )
        print(np.shape(weatherForecastData))
        print(np.shape(intialConditionData))
        # run model
        runningGenerateRiverFlows(
            predictionDate=predictionData,
            dataLocation=location,
            weatherForecast=weatherForecastData,
            initialData=intialConditionData,
            save=False,
        )


@shared_task(name="calculations.dailyModelUpdate")
def dailyModelUpdate():

    print("set up daily model update")


# initialModelSetUp()

# prepareGEFS()
