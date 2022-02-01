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

                                                                                Sim & Jiada
                                                                                01/02/2022
"""

from urllib.request import urlretrieve
import os

# download GEFSdata from ftp server.
rootUrl = "https://ftp.ncep.noaa.gov/data/nccf/com/gens/prod/"
fileDate = "20220131"  # date format: YYYYMMDD
subUrl = "/00/atmos/pgrb2bp5/"
fileName = "gec00.t00z.pgrb2b.0p50.f000"
fullUrl = rootUrl + "gefs." + fileDate + subUrl + fileName
projectPath = os.path.abspath(
    os.path.join((os.path.split(os.path.realpath(__file__))[0]), "../")
)
outPutpath = os.path.join(projectPath, "Data", fileName)
urlretrieve(fullUrl, outPutpath)
