from urllib.request import urlretrieve
import pygrib
import numpy as np


def GEFSdownloader(fileDate, fileName):
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
    :return: none
    """

    # download GEFSdata from ftp server.
    rootUrl = "https://ftp.ncep.noaa.gov/data/nccf/com/gens/prod/"
    subUrl = "/00/atmos/pgrb2ap5/"
    fullUrl = rootUrl + "gefs." + fileDate + subUrl + fileName
    gefsFile = urlretrieve(fullUrl)

    # open GEFS file (type: grib2)
    gefsData = pygrib.open(gefsFile[0])

    print(gefsData[64])
    temp_vals1 = gefsData[64].values
    print(np.shape(temp_vals1))
    print(gefsData[65])
    temp_vals2 = gefsData[65].values
    print(np.shape(temp_vals2))
    print(gefsData[66])
    temp_vals3 = gefsData[66].values
    print(np.shape(temp_vals3))
    print(gefsData[67])
    temp_vals4 = gefsData[67].values
    print(np.shape(temp_vals4))
    print(gefsData[68])
    temp_vals5 = gefsData[68].values
    print(np.shape(temp_vals5))


fileDate = "20220214"  # date format: YYYYMMDD
fileName = "geavg.t00z.pgrb2a.0p50.f240"

gefsFile = GEFSdownloader(fileDate, fileName)


# extract data from GEFS file
# gr = pygrib.open(file)

# msg = gr[65]  # get record number 589
# print(msg)
# extract data from GEFSdata: rainfall, temperature, and Humidity.
