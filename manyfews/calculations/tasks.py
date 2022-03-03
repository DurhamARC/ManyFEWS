from celery import Celery, shared_task
from celery.schedules import crontab
from django_celery_beat.models import CrontabSchedule, PeriodicTask
from .zentra import zentraReader
from .gefs import dataBaseWriter
from django.conf import settings
from .GenerateRiverFlows import (
    prepareGEFSdata,
    prepareInitialCondition,
    GenerateRiverFlows,
)
from django.contrib.gis.geos import Point
from datetime import datetime, timedelta, timezone, date
import os


app = Celery()

import logging

logger = logging.getLogger(__name__)


@shared_task(name="calculations.hello_celery")
def hello_celery():
    """
    This is an example of a task that can be scheduled via celery.
    """
    logger.info("Hello logging from celery!")


@shared_task(name="calculations.prepareGEFS")
def prepareGEFS():
    """
    This function is developed to extract necessary GEFS forecast data sets
    into Database for running the River Flows model
    """
    # prepare GEFS data
    dt = float(settings.GEFS_TIME_STEP)
    forecastDays = int(settings.GEFS_FORECAST_DAYS)
    dataBaseWriter(dt=dt, forecastDays=forecastDays)


@shared_task(name="calculations.prepareZentra")
def prepareZentra():
    """
    This function is developed to extract necessary Zentra cloud observation data sets
    into Database for running the River Flows model
    """

    # get serial number
    stationSN = settings.STATION_SN

    # save into Data base
    backTime = float(settings.ZENTRA_BACKTIME)

    # prepare Zentra Cloud data
    zentraReader(backTime=backTime, stationSN=stationSN)


@shared_task(name="calculations.runningGenerateRiverFlows")
def runningGenerateRiverFlows(dataDate, dataLocation):
    """
    This function is developed to prepare data and running models for generating river flows.

    :param dataDate: the date information of input data
    :param dataLocation: the location information of input data
    :return riverFlowData: it is a data tuple, which:
            riverFlowsData[0] ====> Q
            riverFlowsData[1] ====> t
            riverFlowsData[2] ====> qp
            riverFlowsData[3] ====> Ep
    """
    projectPath = os.path.abspath(
        os.path.join((os.path.split(os.path.realpath(__file__))[0]), "../../")
    )

    dataFileDirPath = os.path.join(projectPath, "Data")
    parametersFilePath = os.path.join(
        dataFileDirPath, "RainfallRunoffModelParameters.csv"
    )

    gefsData = prepareGEFSdata(date=dataDate, location=dataLocation)
    intialConditionData = prepareInitialCondition(date=dataDate, location=dataLocation)

    riverFlowsData = GenerateRiverFlows(
        gefsData=gefsData,
        F0=intialConditionData,
        parametersFilePath=parametersFilePath,
    )

    return riverFlowsData


testDate = datetime(
    year=2010, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
)
testLocation = Point(0, 0)

output = runningGenerateRiverFlows(dataDate=testDate, dataLocation=testLocation)
