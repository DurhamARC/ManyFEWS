import os
import xlrd
import numpy as np
from django.contrib.gis.geos import Point
from datetime import datetime, timedelta, timezone
from .models import NoaaForecast, InitialCondition


def excel_to_matrix(path, sheetNum):
    table = xlrd.open_workbook(path).sheets()[sheetNum]
    row = table.nrows
    col = table.ncols
    datamatrix = np.zeros((row, col))  # ignore the first title row.
    for x in range(1, row):
        #        row = np.matrix(table.row_values(x))
        #        print(type(row))
        row = np.array(table.row_values(x))
        datamatrix[x, :] = row
    datamatrix = np.delete(
        datamatrix, 0, axis=0
    )  # Delete the first blank line.(Its elements are all zero)
    return datamatrix


def prepare_test_GEFS():
    """
    This function is used to import test GEFS data into database.
    It will read data from GEFS xlrd file.
    """

    projectPath = os.path.abspath(
        os.path.join((os.path.split(os.path.realpath(__file__))[0]), "../../")
    )

    dataFileDirPath = os.path.join(projectPath, "Data")
    GefsDataFile = os.path.join(dataFileDirPath, "GEFSdata.xlsx")
    sheetNum = 16
    gefsData = excel_to_matrix(GefsDataFile, sheetNum)
    testDate = datetime(
        year=2010, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
    )
    date = datetime.astimezone(testDate, tz=timezone(timedelta(hours=0)))

    for i in range(len(gefsData[:, 0])):
        testGefsData = NoaaForecast(
            date=date,
            location=Point(0, 0),
            relative_humidity=gefsData[i, 0],
            min_temperature=gefsData[i, 2],
            max_temperature=gefsData[i, 1],
            wind_u=gefsData[i, 3],
            wind_v=gefsData[i, 4],
            precipitation=gefsData[i, 5],
        )
        testGefsData.save()


def prepare_test_initialCondition():
    """
    This function is used to import test initial condition data into database.
    It will read data from 'RainfallRunoffModelInitialConditions' file.
    """

    projectPath = os.path.abspath(
        os.path.join((os.path.split(os.path.realpath(__file__))[0]), "../../")
    )
    dataFileDirPath = os.path.join(projectPath, "Data")
    InitialConditionFile = os.path.join(
        dataFileDirPath, "RainfallRunoffModelInitialConditions.csv"
    )
    F0 = np.loadtxt(open(InitialConditionFile), delimiter=",", usecols=range(3))
    testDate = datetime(
        year=2010, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
    )
    date = datetime.astimezone(testDate, tz=timezone(timedelta(hours=0)))

    for i in range(len(F0[:, 0])):
        testInitialCondition = InitialCondition(
            date=date,
            location=Point(0, 0),
            storage_level=F0[i, 0],
            slow_flow_rate=F0[i, 1],
            fast_flow_rate=F0[i, 2],
        )

        testInitialCondition.save()


# prepare testing GEFS data for model.
prepare_test_GEFS()

# prepare initial conditions for model.
prepare_test_initialCondition()

# import parameters for model.
