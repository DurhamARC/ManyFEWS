from urllib.request import urlretrieve
import pygrib
import numpy as np
from datetime import date, datetime
from datetime import datetime


def GEFSdownloader(fileDate, forecastHour, latValue, lonValue):
    """
    This script is developed to download files, read files, and export necessary data for generating river flows.
    Download from stp server:
    here is an example link (01/02/2022):
    "https://ftp.ncep.noaa.gov/data/nccf/com/gens/prod/gefs.20220201/00/atmos/pgrb2ap5/". There are many files in this
    folder, and all are global at 0.25 degree resolution. The file naming system is:
    gep30.t00z.pgrb2s.0p25.f240
    gep = global ensemble prediction
    30 = ensemble number. In this case it was the 30th member.
    t00z = not sure, but they all have this code so we do not need to adjust for it.
    pgrb2s = the number of weather forecast variables
    0p25 = this means it is the 0.25 degree resolution model
    f240 = number of hours into the future that the forecast is for.

    :param fileDate: the select date of file with format: YYYYMMDD (only three days back)
    :param fileName: the name of GEFS file. ( e.g. geavg.t00z.pgrb2a.0p50.f240)
    :param latValue: the latitude of the specific cell.
                    (the solution is 0.5 degree. range [-90, 90] with 0.5 interval)
    :param lonValue: the longtitue of the specific cell.
                    (the solution is 0.5 degree, range [-180, 180] with 0.5 interval)
    :return: the GEFS data at the specific location and date.
                0.Relative Humidity.
                1.Maximum Temperature.
                2.Minimum Temperature.
                3.U Wind Component.
                4.V Wind Component.
                5.Total Precipitation.
    """

    # download GEFSdata from ftp server.
    rootUrl = "https://ftp.ncep.noaa.gov/data/nccf/com/gens/prod/"
    subUrl = "/00/atmos/pgrb2ap5/"
    fileNameBase = "geavg.t00z.pgrb2a.0p50.f"
    fileName = fileNameBase + (str(forecastHour)).zfill(3)
    fullUrl = rootUrl + "gefs." + fileDate + subUrl + fileName
    gefsFile = urlretrieve(fullUrl)
    gefsData = pygrib.open(gefsFile[0])

    # extract necessary data sets:
    for grb in gefsData:

        # metre relative humidity, unit:% (instant).
        if grb.parameterName == "Relative humidity" and grb.level == 2:
            lats, lons = grb.latlons()
            index = cellIndexFinder(
                latitudeInfo=lats,
                longitudeInfo=lons,
                latValue=latValue,
                lonValue=lonValue,
            )
            RHvalue = grb.values[index]

        # Maximum temperature: unit:K (max).
        elif grb.parameterName == "Maximum temperature" and grb.level == 2:
            lats, lons = grb.latlons()
            index = cellIndexFinder(
                latitudeInfo=lats,
                longitudeInfo=lons,
                latValue=latValue,
                lonValue=lonValue,
            )
            maxTempValue = grb.values[index]

        # Minimum temperature: unit:K (min).
        elif grb.parameterName == "Minimum temperature" and grb.level == 2:
            lats, lons = grb.latlons()
            index = cellIndexFinder(
                latitudeInfo=lats,
                longitudeInfo=lons,
                latValue=latValue,
                lonValue=lonValue,
            )
            minTempValue = grb.values[index]

        # metre U wind component: unit:m/s (instant).
        elif grb.parameterName == "u-component of wind" and grb.level == 10:
            lats, lons = grb.latlons()
            index = cellIndexFinder(
                latitudeInfo=lats,
                longitudeInfo=lons,
                latValue=latValue,
                lonValue=lonValue,
            )
            uWindValue = grb.values[index]

        # metre V wind component: unit:m/s (instant).
        elif grb.parameterName == "v-component of wind" and grb.level == 10:
            lats, lons = grb.latlons()
            index = cellIndexFinder(
                latitudeInfo=lats,
                longitudeInfo=lons,
                latValue=latValue,
                lonValue=lonValue,
            )
            vWindValue = grb.values[index]

        # Total Precipitation: unit:kg/m2 (accum).
        elif grb.parameterName == "Total precipitation" and grb.level == 0:
            lats, lons = grb.latlons()
            index = cellIndexFinder(
                latitudeInfo=lats,
                longitudeInfo=lons,
                latValue=latValue,
                lonValue=lonValue,
            )
            totalPrecipValue = grb.values[index]

    return RHvalue, maxTempValue, minTempValue, uWindValue, vWindValue, totalPrecipValue


def cellIndexFinder(latitudeInfo, longitudeInfo, latValue, lonValue):
    """
    This function is developed for finder the index of the specific cell in gefs data.

    :param latitudeInfo: the latitude matrix of the grid.
    :param longitudeInfo: the longtitude matrix of the grid.
    :param latValue: the latitude of the specific cell
    :param lonValue: the longitude of the specific cell
    :return: the index of the cell location.
    """

    # find the Index of the specific location in gefs data.
    latsIndex = np.where(latitudeInfo == latValue)
    lonsIndex = np.where(longitudeInfo == lonValue)
    index = (latsIndex[0][0], lonsIndex[1][0])

    return index


for i in range(1):
    # forcastHour = 6 + i*6
    forcastHour = 3
    gefsData = GEFSdownloader(
        fileDate="20220216", forecastHour=forcastHour, latValue=-80.5, lonValue=175
    )

    print(forcastHour, gefsData[0], gefsData[1], gefsData[2], gefsData[3], gefsData[4])
