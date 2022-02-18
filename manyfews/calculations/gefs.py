from urllib.request import urlretrieve
import pygrib
import numpy as np


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
    fileName = fileNameBase + str(forecastHour)
    fullUrl = rootUrl + "gefs." + fileDate + subUrl + fileName
    gefsFile = urlretrieve(fullUrl)
    gefsData = pygrib.open(gefsFile[0])

    # extract necessary data sets:
    RH = gefsData[64]  # metre relative humidity, unit:% (instant).
    maxTemp = gefsData[65]  # Maximum temperature: unit:K (max).
    minTemp = gefsData[66]  # Minimum temperature: unit:K (min).
    uWind = gefsData[67]  # metre U wind component: unit:m/s (instant).
    vWind = gefsData[68]  # metre V wind component: unit:m s**-1 (instant).
    totalPrecip = gefsData[69]  # Total Precipitation: unit:kg/m2 (accum).

    lats, lons = RH.latlons()  # obtain information on latitude & longitude.

    # find the Index of the specific location in gefs data.
    latsIndex = np.where(lats == latValue)
    lonsIndex = np.where(lons == lonValue)
    index = (latsIndex[0][0], lonsIndex[1][0])

    # extract values of the specific point.
    RHvalue = RH.values[index]
    maxTempValue = maxTemp.values[index]
    minTempValue = minTemp.values[index]
    uWindValue = uWind.values[index]
    vWindValue = vWind.values[index]
    totalPrecipValue = totalPrecip.values[index]

    return RHvalue, maxTempValue, minTempValue, uWindValue, vWindValue, totalPrecipValue


gefsData = GEFSdownloader(
    fileDate="20220215", forecastHour=240, latValue=-80.5, lonValue=175
)

print(gefsData[0])
