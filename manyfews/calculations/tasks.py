from celery import Celery, shared_task
from celery.schedules import crontab
from django_celery_beat.models import CrontabSchedule, PeriodicTask
from .zentra import zentraReader, offsetTime, aggregateZentraData
from django.conf import settings
from .models import AggregatedZentraReading, InitialCondition, NoaaForecast
from .generate_river_flows import (
    prepareWeatherForecastData,
    runningGenerateRiverFlows,
    prepareInitialCondition,
    GenerateRiverFlows,
)
from django.contrib.gis.geos import Point
from .zentra import prepareZentra, offsetTime
from .gefs import prepareGEFS
from datetime import datetime, date, timedelta, timezone
import os
from tqdm import trange
from datetime import timedelta
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
    """
    Initial model set up
    This is part is only run once when the application is just installed.

    1. Start with all parameters at their default values. These are the default value that Simon passed to you.
    2. Get the last 365 days of data from the catchment via Zentra
    3. Run the model for this dataset
    4. The model will write out the initial conditions for each of the model parameter sets.
       This is the file that we will use for the next day in the processing.

    """

    backDays = int(settings.INITIAL_BACKTIME)
    timeInfo = offsetTime(backDays=backDays)
    location = Point(0, 0)

    # prepare the time point for getting zentra data.
    # For initial model setup, it needs 365 days zentra data.
    for backDay in trange(backDays, 0, -1):
        prepareZentra(backDay=backDay)

    # prepare weather data (from Zentra).
    weatherForecastData = prepareWeatherForecastData(
        predictionDate=timeInfo[0], location=location, dataSource="zentra", backDays=365
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
    3. Run the model for one day with the new data
    4. Write the new initial conditions for today.
    Part 2
    1. Put together all of the time series from GEFS – there are 21 in total.
    2. Run the model with the new initial conditions (from step 4 directly above) for each of the weather
       forecast time series from step one above
    3. We now have a set of ca. 2100 time series of river flow forecast for the next 16 days.

    """

    ## Part 1
    # prepare time and location info
    location = Point(0, 0)
    yday = offsetTime(backDays=1)
    today = offsetTime(backDays=0)

    # Check whether zentra data has been downloaded
    aggregateData = AggregatedZentraReading.objects.filter(
        date__range=(yday[0], yday[1])
    ).filter(location=location)

    if len(aggregateData) == 0:
        # Get the last day’s data from Zentra
        prepareZentra(backDay=1)

    ydayZentra = prepareWeatherForecastData(
        predictionDate=yday[0], location=location, dataSource="zentra", backDays=1
    )

    # Read in the initial conditions from the previous day
    initialConditions = InitialCondition.objects.filter(date=today[0]).filter(
        location=location
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
        initialData=F0,
        riverFlowSave=True,
        initialDataSave=True,
        mode="daily",
    )
