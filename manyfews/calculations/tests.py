from django.contrib.gis.geos import Point
from django.test import TestCase

from .models import (
    ZentraReading,
    NoaaForecast,
    InitialCondition,
    AggregatedZentraReading,
)
from django.test import TestCase
import numpy as np
from django.contrib.gis.geos import Point
from datetime import datetime, timezone
from .tasks import initialModelSetUp
from .zentra import offsetTime
import xlrd
import os


def excel_to_matrix(path, sheetNum):
    """
    This function is used to convert data form from excel (.xlsx) into a Numpy array.

    :param path: the absolute path of the excel file.
    :param sheetNum: the sheet number of the table in the excel file.

    """

    table = xlrd.open_workbook(path).sheets()[sheetNum]
    row = table.nrows
    col = table.ncols
    datamatrix = np.zeros((row, col))  # ignore the first title row.
    for x in range(1, row):
        #        row = np.matrix(table.row_values(x))
        row = np.array(table.row_values(x))
        datamatrix[x, :] = row
    datamatrix = np.delete(
        datamatrix, 0, axis=0
    )  # Delete the first blank line.(Its elements are all zero)
    return datamatrix


def prepare_test_Data():
    """
    This function is used to import test GEFS and initial condition data into database.

    1. For GEFS: It will read data from GEFS xlrd file (GEFSdata) in Data directory.
    2. For initial condition: It will read data from csv file ( 'RainfallRunoffModelInitialConditions.csv')
    in Data directory.

    return: a tuple of test information, which includes: test date and test location.
            [0]: test date
            [1]: test location
    """

    projectPath = os.path.abspath(
        os.path.join((os.path.split(os.path.realpath(__file__))[0]), "../../")
    )

    dataFileDirPath = os.path.join(projectPath, "Data")
    GefsDataFile = os.path.join(dataFileDirPath, "GEFSdata.xlsx")
    InitialConditionFile = os.path.join(
        dataFileDirPath, "RainfallRunoffModelInitialConditions.csv"
    )

    # prepare test date information
    testDate = datetime(
        year=2010, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
    )
    date = datetime.astimezone(testDate, tz=timezone.utc)

    # prepare test location information (fake)
    testLocation = Point(0, 0)

    # prepare test GEFS data
    sheetNum = 16
    gefsData = excel_to_matrix(GefsDataFile, sheetNum)

    # save into DB ( 'calculations_noaaforecast' table)
    for i in range(len(gefsData[:, 0])):
        testGefsData = NoaaForecast(
            date=date,
            location=testLocation,
            relative_humidity=gefsData[i, 0],
            min_temperature=gefsData[i, 2],
            max_temperature=gefsData[i, 1],
            wind_u=gefsData[i, 3],
            wind_v=gefsData[i, 4],
            precipitation=gefsData[i, 5],
        )
        testGefsData.save()

    # prepare initial condition data
    F0 = np.loadtxt(open(InitialConditionFile), delimiter=",", usecols=range(3))

    # save into DB ( 'calculations_initialcondition' table)
    for i in range(len(F0[:, 0])):
        testInitialCondition = InitialCondition(
            date=date,
            location=testLocation,
            storage_level=F0[i, 0],
            slow_flow_rate=F0[i, 1],
            fast_flow_rate=F0[i, 2],
        )

        testInitialCondition.save()

    return testDate, testLocation


class taskTest(TestCase):
    def test_initialModelSetUp(self):
        """
        Test the inital Model SetUp task.
        """
        initialModelSetUp()

        # Check that there are readings (past 365 days) in the database

        timeInfo = offsetTime(backDays=365)
        startTime = timeInfo[0]
        endTime = timeInfo[1]

        readings = ZentraReading.objects.filter(date__range=(startTime, endTime))
        aggregateReading = AggregatedZentraReading.objects.filter(
            date__range=(startTime, endTime)
        )

        assert len(readings) == 105070
        assert len(aggregateReading) == 1460

        # check that there are inidtial condition  in the database
        initialcondition = InitialCondition.objects.all()

        assert len(initialcondition) == 100
