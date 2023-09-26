import logging

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

    # Indices to interpolate if ZENTRA_INTERPOLATE_MISSING is True
    interpolation_indices = []

    precip = []
    wDirection = []
    wSpeed = []
    airTem = []
    convertedDate = []
    rh = []

    # Variables used in data preparation:
    kind_strings = [
        "Precipitation",
        "Wind Direction",
        "Wind Speed",
        "Air Temperature",
        "Vapour Pressure",
    ]
    clamp = lambda n, minn, maxn: max(min(maxn, n), minn)

    # Check that we have data
    try:
        len(zentraData["device"]["timeseries"][0]["configuration"]["values"])

    except IndexError as e:
        if len(zentraData["device"]["timeseries"]) == 0:
            raise IndexError(
                "Error preparing Zentra Cloud data.\n\t"
                + f"No data was received from Zentra for the device {stationSN}.\n\t"
                + "Ensure the station is logging and uploading data to Zentra, "
                + "or provide a different station."
            ) from e
        raise e

    data = zentraData["device"]["timeseries"][0]["configuration"]["values"]

    try:
        # Extract time stamp, Precipitation, solar, temperature, and humidity
        for i, d in enumerate(data):

            # convert time stamp to Date
            ts = d[0]  # time stamp
            date = datetime.fromtimestamp(
                ts, tz=timezone.utc
            )  # change time stamp to UTC time.

            # Check data: the series we want are at indices 1, 4, 5, 7, 8
            error = False
            for kind, j in enumerate([1, 4, 5, 7, 8]):
                # kinds[k] is string of kind, j is index into data
                if d[3][j]["error"]:
                    logging.debug(
                        f"ZentraDevice {kind_strings[kind]} error at index {i}: {d[3][j]['description']}"
                    )
                    error = True

            # If data is bad, don't process this entry
            if error:
                if settings.ZENTRA_FAIL_ON_MISSING:
                    raise RuntimeError(
                        f"Bad data at index {i} in ZentraData for {date}\n"
                        f"The Zentra device {stationSN} is missing data.\n"
                        f"This program is configured not to operate on partial data "
                        f"(ZENTRA_INTERPOLATE_MISSING is False).\n"
                        "Select another Zentra Device or check the device's connection."
                    )
                elif settings.ZENTRA_INTERPOLATE_MISSING:
                    logging.warning(
                        f"Missing value at index {i} in ZentraData for {date}. "
                        "Interpolation will be attempted."
                    )

                    # Mark as interpolation start point
                    interpolation_indices.append(i)
                    convertedDate.append(date)
                    precip.append(np.nan)
                    airTem.append(np.nan)
                    wDirection.append(np.nan)
                    wSpeed.append(np.nan)
                    rh.append(np.nan)
                    continue

            convertedDate.append(date)
            precip.append(d[3][1]["value"])  # Precipitation, 'unit':' mm'
            airTem.append(d[3][7]["value"])  # air temperature, 'unit'=' °C'
            wDirection.append(d[3][4]["value"])  # Wind Direction, 'units': ' °'
            wSpeed.append(d[3][5]["value"])  # wind speed, 'units': ' m/s'

            # calculate rh by: esTair = 0.611*EXP((17.502*Tc)/(240.97+Tc))
            #                  rh = VP / esTair
            #                 which:Tc is the Air Temperature
            #                       VP is the Vapour Pressure
            #                       rh is the Relative Humidity between zero and one.
            tempAir = d[3][7]["value"]
            vapPressure = d[3][8]["value"]

            # Missing data will be strings of value "None"
            if type(tempAir) is str and tempAir == "None":
                rh.append("None")
                continue

            relative_hum = vapPressure / (
                0.611 * (math.exp((17.502 * tempAir) / (240.97 + tempAir)))
            )
            rh.append(clamp(relative_hum, 0, 1))

    except TypeError as e:
        raise TypeError("Error in environmental data calculation.") from e

    zentraDevice = ZentraDevice.objects.get(device_sn=stationSN)

    # Interpotate values (if switched on)
    if len(interpolation_indices):
        precip, rh, airTem, wSpeed, wDirection = interpolate_missing_data(
            interpolation_indices, [precip, rh, airTem, wSpeed, wDirection]
        )

    # converting string 'None' to None by strNoneToNone method.
    precip = list(map(strNoneToNone, precip))
    rh = list(map(strNoneToNone, rh))
    airTem = list(map(strNoneToNone, airTem))
    wSpeed = list(map(strNoneToNone, wSpeed))
    wDirection = list(map(strNoneToNone, wDirection))

    # import data into DB
    for i in range(len(convertedDate)):
        zentraData = ZentraReading(
            date=convertedDate[i],
            device=zentraDevice,
            precipitation=precip[i],
            relative_humidity=rh[i],
            air_temperature=airTem[i],
            wind_speed=wSpeed[i],
            wind_direction=wDirection[i],
        )

        zentraData.save()


def interpolate_missing_data(null_indices: list, series: list):
    """
    Perform linear interpolation of missing values.
    This functionality can be switched on using the environment variable
    ZENTRA_INTERPOLATE_MISSING = True on the command line.
    @param null_indices:
    @param series: [precip, rh, airTem, wSpeed, wDirection]
    @return:
    """
    logging.debug(f"Filling indices: \n{null_indices}")

    new_series = []
    # For the null indices, interpolate data
    for i, s in enumerate(series):
        # logging.debug(s)
        data_array = np.array(s)
        non_null_mask = ~np.isnan(data_array)

        # Use linear interpolation to fill null values
        data_array[null_indices] = np.interp(
            null_indices,
            np.arange(len(data_array))[non_null_mask],
            data_array[non_null_mask],
        )

        # Append resulting dataset with linearly interpolated values to return list
        new_series.append(data_array.tolist())

    return new_series


def aggregateZentraData(startTime, endTime, stationSN):
    """
    Aggregate Zentra Data for use within the flood model
    Converts
    @param startTime:
    @param endTime:
    @param stationSN:
    @return:
    """
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

    # Data cleaning:
    #  defaults value when zentra does not report a value
    defaultsRH = settings.DEFAULT_RH
    defaultsAirTemp = settings.DEFAULT_AIR_TEMP
    defaultPrecip = settings.DEFAULT_PRECIP

    # convert temperature Unit from °C to ˚K
    defaultsAirTemp = [i + 273.15 for i in defaultsAirTemp]

    # get month info
    monthNO = startTime.month

    defaultsRHvalue = defaultsRH[monthNO - 1]  # start from 0
    defaultPrecipVlue = defaultPrecip[monthNO - 1]
    defaultsAirTempValue = defaultsAirTemp[monthNO - 1]

    wSpeedList = [
        1 if i == None else i for i in wSpeedList
    ]  # for None data, set it to default (1)
    wDirectionList = [
        1 if i == None else i for i in wDirectionList
    ]  # for None data, set it to default (1)
    airTemList = [
        defaultsAirTempValue if i == None else i for i in airTemList
    ]  # for None data, set it to defaults
    precipList = [
        defaultPrecipVlue if i == None else i for i in precipList
    ]  # for None data, set it to defaults
    RHList = [
        defaultsRHvalue if i == None else i for i in RHList
    ]  # for None data, set it to defaults

    # Convert values
    # convert temperature Unit from °C to ˚K
    airTemList = [i + 273.15 for i in airTemList]

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
        aggregatedData[i, 5] = np.sum(intervalData[:, 1])  # sum result of precipitation
        aggregatedData[i, 1] = np.max(
            intervalData[:, 2]
        )  # find the maximum temperature
        aggregatedData[i, 2] = np.min(
            intervalData[:, 2]
        )  # find the minimum temperature

    location = zentraReadingData[0].device.location

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

    startDate = datetime.utcnow() - timedelta(days=backDays)

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
