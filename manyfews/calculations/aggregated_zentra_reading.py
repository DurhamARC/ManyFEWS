from .models import ZentraReading, AggregatedZentraReading
from datetime import datetime, timedelta, timezone
from django.conf import settings
import numpy as np
import math


# extract data from ZentraReading table.
beginTime = datetime(
    year=2021,
    month=3,
    day=12,
    hour=0,
    minute=0,
    second=0,
    microsecond=0,
    tzinfo=timezone(timedelta(hours=0)),
)

endTime = datetime(
    year=2021,
    month=3,
    day=12,
    hour=23,
    minute=55,
    second=0,
    microsecond=0,
    tzinfo=timezone(timedelta(hours=0)),
)

sn = "06-02047"


def aggregateZentraData(stationSN, beginTime, endTime):

    # extract data from DB and export data into a Numpy array.
    zentraReadingData = ZentraReading.objects.filter(
        date__range=(beginTime, endTime)
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

    zentraReadingList = list(
        zip(RHList, precipList, airTemList, wSpeedList, wDirectionList)
    )

    zentraData = np.array(zentraReadingList)

    #
    #  filter the wrong data
    #

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
        date = beginTime + timedelta(days=(dt * i))
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


aggregateZentraData(stationSN=sn, beginTime=beginTime, endTime=endTime)
