from celery import Celery, shared_task
from celery.schedules import crontab
from django_celery_beat.models import CrontabSchedule, PeriodicTask
from .zentra import zentraReader
from .gefs import dataBaseWriter
from django.conf import settings
from .models import (
    InitialCondition,
    RainAndEvapotranspiration,
    PotentialRiverFlows,
)
from .generate_river_flows import (
    prepareGEFSdata,
    prepareInitialCondition,
    GenerateRiverFlows,
)
from datetime import datetime, timedelta, timezone
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
def runningGenerateRiverFlows(dt, beginDate, dataLocation):
    """
    This function is developed to prepare data and running models for generating river flows,
    and save the next day's initial condition, River flow, Rainfall, and potential evapotranspiration
    into DB.

    :param dt: time step(unit:day)
    :param beginDate: the date information of input data.
    :param dataLocation: the location information of input data
    :return none.
    """
    projectPath = os.path.abspath(
        os.path.join((os.path.split(os.path.realpath(__file__))[0]), "../../")
    )

    dataFileDirPath = os.path.join(projectPath, "Data")
    parametersFilePath = os.path.join(
        dataFileDirPath, "RainfallRunoffModelParameters.csv"
    )

    # plus time zone information
    beginDate = datetime.astimezone(beginDate, tz=timezone(timedelta(hours=0)))

    # prepare GEFS data for model.
    gefsData = prepareGEFSdata(date=beginDate, location=dataLocation)

    # prepare initial condition data for model.
    initialConditionData = prepareInitialCondition(
        date=beginDate, location=dataLocation
    )

    # run model.
    riverFlowsData = GenerateRiverFlows(
        dt=0.25,
        gefsData=gefsData,
        F0=initialConditionData,
        parametersFilePath=parametersFilePath,
    )

    # riverFlowsData[0] ====> Q: River flow (m3/s).
    # riverFlowsData[1] ====> qp: Rainfall (mm/day).
    # riverFlowsData[2] ====> Ep: Potential evapotranspiration (mm/day).
    # riverFlowsData[3] ====> F0: intial condition data for next day.

    riverFlows = riverFlowsData[0]
    qp = riverFlowsData[1]
    Ep = riverFlowsData[2]
    F0 = riverFlowsData[3]  # next day's initial condition

    # import the next day's initial condition data F0 into DB.
    # ('calculations_initialcondition' table)
    nextDay = beginDate + timedelta(days=1)
    for i in range(len(F0[:, 0])):
        nextDayInitialCondition = InitialCondition(
            date=nextDay,
            location=dataLocation,
            storage_level=F0[i, 0],
            slow_flow_rate=F0[i, 1],
            fast_flow_rate=F0[i, 2],
        )
        nextDayInitialCondition.save()

    for i in range(qp.shape[0]):
        # save qp and Eq and into DB.
        # ( 'calculations_rainandevapotranspiration' table)
        dataDate = beginDate + timedelta(dt * i)
        RainAndEvapotranspirationData = RainAndEvapotranspiration(
            date=dataDate,
            location=dataLocation,
            rain_fall=qp[i],
            potential_evapotranspiration=Ep[i],
        )
        RainAndEvapotranspirationData.save()

        # save Q into DB.
        # ('calculations_potentialriverflows' table)
        for j in range(riverFlows.shape[1]):
            PotentialRiverFlowsData = PotentialRiverFlows(
                date=dataDate, location=dataLocation, river_flows=riverFlows[i, j],
            )
            PotentialRiverFlowsData.save()
