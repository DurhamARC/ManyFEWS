from .models import ZentraReading
from zentra.api import ZentraReadings, ZentraToken
from datetime import timedelta, timezone, datetime
from django.conf import settings
from .models import ZentraDevice, AggregatedZentraReading
import numpy as np
import math


def zentraReader(startTime, endTime, stationSN):

    """
    This function is used to extract observation climate data from ZENTRA cloud: https://zentracloud.com/,
    and output data sets into Database ( calculations_zentrareading table)

    :param startTime: the start time you want to extract (unit: day).
    :param endTime: the end time you want to extract (unit: day).
    :param stationSN: the serial number of meter station.
    :param token: authentication token.
    :return none

    """
    # return authentication token for the Zentra cloud
    token = ZentraToken(username=settings.ZENTRA_UN, password=settings.ZENTRA_PW)

    # Get the readings for a device
    readings = ZentraReadings().get(
        sn=stationSN,
        token=token,
        start_time=int(startTime.timestamp()),
        end_time=int(endTime.timestamp()),
    )
    zentraData = readings.response

    precip = []
    wDirection = []
    wSpeed = []
    airTem = []
    convertedDate = []
    RH = []

    # Extract time stamp, Precipitation, solar, temperature, and humidity
    for i in range(
        len(zentraData["device"]["timeseries"][0]["configuration"]["values"])
    ):

        precip.append(
            zentraData["device"]["timeseries"][0]["configuration"]["values"][i][3][1][
                "value"
            ]
        )  # Precipitation, 'unit':' mm'

        airTem.append(
            zentraData["device"]["timeseries"][0]["configuration"]["values"][i][3][7][
                "value"
            ]
        )  # air temperature, 'unit'=' °C'

        wDirection.append(
            zentraData["device"]["timeseries"][0]["configuration"]["values"][i][3][4][
                "value"
            ]
        )  # Wind Direction, 'units': ' °'

        wSpeed.append(
            zentraData["device"]["timeseries"][0]["configuration"]["values"][i][3][5][
                "value"
            ]
        )  # wind speed, 'units': ' m/s'

        # convert time stamp to Date
        ts = zentraData["device"]["timeseries"][0]["configuration"]["values"][i][
            0
        ]  # time stamp
        date = datetime.fromtimestamp(
            ts, tz=timezone.utc
        )  # change time stamp to UTC time.
        convertedDate.append(date)

        # calculate RH by: esTair = 0.611*EXP((17.502*Tc)/(240.97+Tc))
        #                  RH = VP / esTair
        #                 which:Tc is the Air Temperature
        #                       VP is the Vapour Pressure
        #                       RH is the Relative Humidity between zero and one.

        Tempair = zentraData["device"]["timeseries"][0]["configuration"]["values"][i][
            3
        ][7]["value"]

        vapPressure = zentraData["device"]["timeseries"][0]["configuration"]["values"][
            i
        ][3][8]["value"]
        rh = vapPressure / (0.611 * (math.exp((17.502 * Tempair) / (240.97 + Tempair))))

        if rh > 1:
            rh = 1
        elif rh < 0:
            rh = 0

        RH.append(rh)

    zentraDevice = ZentraDevice.objects.get(device_sn=stationSN)

    # converting string 'None' to None by strNoneToNone method.
    precip = list(map(strNoneToNone, precip))
    RH = list(map(strNoneToNone, RH))
    airTem = list(map(strNoneToNone, airTem))
    wSpeed = list(map(strNoneToNone, wSpeed))
    wDirection = list(map(strNoneToNone, wDirection))

    # import data into DB
    for i in range(len(convertedDate)):
        zentraData = ZentraReading(
            date=convertedDate[i],
            device=zentraDevice,
            precipitation=precip[i],
            relative_humidity=RH[i],
            air_temperature=airTem[i],
            wind_speed=wSpeed[i],
            wind_direction=wDirection[i],
        )

        zentraData.save()


def aggregateZentraData(startTime, endTime, stationSN):

    # extract data from DB and export data into a Numpy array.
    zentraReadingData = ZentraReading.objects.filter(
        date__range=(startTime, endTime)
    ).filter(device_id=stationSN)

    precipList = []
    wDirectionList = []
    wSpeedList = []
    airTemList = []
    RHList = []

    for data in zentraReadingData:
        RHList.append(data.relative_humidity)
        precipList.append(data.precipitation)
        airTemList.append(data.air_temperature)
        wSpeedList.append(data.wind_speed)
        wDirectionList.append(data.wind_direction)

    # convert temperature Unit from °C to ℉
    airTemList = [i + 273.15 for i in airTemList]

    ##############################################
    #  filter the wrong data (Temporary solution)
    #############################################
    wSpeedList = [
        1 if i == None else i for i in wSpeedList
    ]  # for None data, set it to default (1)
    wDirectionList = [
        1 if i == None else i for i in wDirectionList
    ]  # for None data, set it to default (1)
    ###############################################

    zentraReadingList = list(
        zip(RHList, precipList, airTemList, wSpeedList, wDirectionList)
    )

    zentraData = np.array(zentraReadingList)

    # Convert wind speed and wind direction into Uwind and Vwind
    wSpeed = zentraData[:, 3]
    wDirection = zentraData[:, 4]

    # calculation of Uwind and Vwind
    wDirection = (wDirection * (math.pi)) / 180  # Convert angle to magnitude

    uWind = (np.cos(wDirection)) * wSpeed
    vWind = (np.sin(wDirection)) * wSpeed
    zentraData[:, 3] = uWind
    zentraData[:, 4] = vWind

    # aggregate zentra data within every 6(dt) hours: 6 hours (dt =0.25 unit:day)
    dt = float(settings.MODEL_TIMESTEP)
    intervalNum = int(1 / dt)  # the number of aggregating points per day.
    dataPointNum = int(
        (len(zentraData)) / intervalNum
    )  # the number of data sets per aggregation

    aggregatedData = np.zeros([intervalNum, 6], dtype=float)
    for i in range(intervalNum):

        # get the array sequence of data for each aggregating period
        seq = range(i * dataPointNum, ((i + 1) * dataPointNum))
        intervalData = zentraData[np.array(tuple(seq))]
        aggregatedData[i, 0] = np.mean(intervalData[:, 0])  # mean result of RH
        aggregatedData[i, 3] = np.mean(intervalData[:, 3])  # mean result of uWind
        aggregatedData[i, 4] = np.mean(intervalData[:, 4])  # mean result of vWind
        aggregatedData[i, 5] = np.mean(
            intervalData[:, 1]
        )  # mean result of precipitation
        aggregatedData[i, 1] = np.max(
            intervalData[:, 2]
        )  # find the maximum temperature
        aggregatedData[i, 2] = np.min(
            intervalData[:, 2]
        )  # find the minimum temperature

    from django.contrib.gis.geos import Point

    location = Point(0, 0)

    for i in range(len(aggregatedData)):
        date = startTime + timedelta(days=(dt * i))

        # plus time zone information
        date = date.astimezone(tz=timezone.utc)

        aggregatedZentraData = AggregatedZentraReading(
            date=date,
            location=location,
            relative_humidity=aggregatedData[i, 0],
            min_temperature=aggregatedData[i, 2],
            max_temperature=aggregatedData[i, 1],
            wind_u=aggregatedData[i, 3],
            wind_v=aggregatedData[i, 4],
            precipitation=aggregatedData[i, 5],
        )
        aggregatedZentraData.save()


def strNoneToNone(x):
    """
    create a method for converting string type to None Type
    """

    if type(x) == str:
        x = None

    return x


def offsetTime(backDays):
    """
    This function is offset the datetime to the day's 00:00 & 23:55
    :param backDays: the number of previous days you want to extract from zentra cloud.

    """

    startDate = datetime.now() - timedelta(days=backDays)

    startTime = datetime(
        year=startDate.year,
        month=startDate.month,
        day=startDate.day,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=timezone.utc,
    )  # Offset start time to 00:00

    endTime = datetime(
        year=startDate.year,
        month=startDate.month,
        day=startDate.day,
        hour=23,
        minute=55,
        second=0,
        microsecond=0,
        tzinfo=timezone.utc,
    )  # Offset start time to 23:55

    return startTime, endTime


def prepareZentra(backDay=1):
    """
    This function is developed to extract daily necessary Zentra cloud observation data sets
    into Database and aggregate data for running the River Flows model.

    :param backDay: the number of previous days you want to extract from zentra cloud. (default = 1)
    For each day: the data is from 00:00 ---> 23:55
    """

    # get serial number
    stationSN = settings.STATION_SN

    # prepare start_time and end_time
    timeInfo = offsetTime(backDays=backDay)
    startTime = timeInfo[0]
    endTime = timeInfo[1]

    # prepare Zentra Cloud data
    zentraReader(startTime=startTime, endTime=endTime, stationSN=stationSN)

    # aggregate zentra data
    aggregateZentraData(startTime=startTime, endTime=endTime, stationSN=stationSN)
