from django.contrib.gis.geos import Point
from django.test import TestCase

from .models import (
    ZentraDevice,
    ZentraReading,
    NoaaForecast,
    InitialCondition,
    RiverFlowCalculationOutput,
    RiverFlowPrediction,
)
from .tasks import prepareZentra, prepareGEFS, runningGenerateRiverFlows
from django.test import TestCase
import numpy as np
from django.contrib.gis.geos import Point
from datetime import datetime, timedelta, timezone
from .generate_river_flows import (
    prepareGEFSdata,
    prepareInitialCondition,
)
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
        #        print(type(row))
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
    date = datetime.astimezone(testDate, tz=timezone(timedelta(hours=0)))

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


class WeatherImportTests(TestCase):
    def test_fetch_from_zentra(self):
        # Check that the prepareZentra task can run and adds some records to the db
        sn = "06-02047"
        zentraDevice = ZentraDevice(sn, location=Point(0, 0))
        zentraDevice.save()

        prepareZentra()

        # Check that there are readings in the database
        readings = ZentraReading.objects.all()
        assert len(readings) == 288

        # Check that they all relate to our device
        for reading in readings:
            assert reading.device == zentraDevice

    def test_fetch_from_GEFS(self):
        # Check that the prepareGEFS task can run and adds some records to the db
        prepareGEFS()

        # Check that there are readings in the database
        readings = NoaaForecast.objects.all()
        assert len(readings) == 64


class ModelCalculationTests(TestCase):
    def test_calculation_GenerateRiverFlow(self):
        testInfo = prepare_test_Data()  # get test data and location
        testDate = testInfo[0]  # date
        testLocation = testInfo[1]  # location

        # plus time zone information
        testDate = datetime.astimezone(testDate, tz=timezone(timedelta(hours=0)))
        nextDay = testDate + timedelta(days=1)

        gefsData = prepareGEFSdata(date=testDate, location=testLocation)

        # prepare initial condition data for model.
        initialConditionData = prepareInitialCondition(
            date=testDate, location=testLocation
        )
        runningGenerateRiverFlows(
            predictionDate=testDate,
            dataLocation=testDate,
            weatherForecast=gefsData,
            initialData=initialConditionData,
        )

        # runningGenerateRiverFlows(predictionDate=testDate, dataLocation=testLocation)

        # extract result from data base.
        riverFlowCalculationOutputData = RiverFlowCalculationOutput.objects.all()
        riverFlowPredictionData = RiverFlowPrediction.objects.all()
        initialConditions = InitialCondition.objects.filter(date=nextDay).filter(
            location=testLocation
        )

        qpList = []
        EpList = []
        QList = []
        slowFlowRateList = []
        fastFlowRateList = []
        storageLevelList = []

        for data in riverFlowCalculationOutputData:
            qpList.append(data.rain_fall)
            EpList.append(data.potential_evapotranspiration)

        # reform data into a Numpy array.
        qp = np.array(qpList)
        Ep = np.array(EpList)

        for data in riverFlowPredictionData:
            QList.append(data.river_flow)

        # reform data into a Numpy array.
        Q = np.array(QList)
        Q.resize((64, 100))

        # extract output initial condition of river flows model.
        for data in initialConditions:
            slowFlowRateList.append(data.slow_flow_rate)
            fastFlowRateList.append(data.fast_flow_rate)
            storageLevelList.append(data.storage_level)
        initialConditionsList = list(
            zip(storageLevelList, slowFlowRateList, fastFlowRateList)
        )
        F0 = np.array(initialConditionsList)

        # get the reference results
        projectPath = os.path.abspath(
            os.path.join((os.path.split(os.path.realpath(__file__))[0]), "../../")
        )

        dataFileDirPath = os.path.join(projectPath, "Data")

        Qbenchmark = np.loadtxt(
            open(os.path.join(dataFileDirPath, "Q_Benchmark.csv")),
            delimiter=",",
            usecols=range(100),
        )
        F0benchmark = np.loadtxt(
            open(os.path.join(dataFileDirPath, "F0_Benchmark.csv")), usecols=range(3),
        )
        qpbenchmark = np.loadtxt(
            open(os.path.join(dataFileDirPath, "qp_Benchmark.csv")),
            delimiter=",",
            usecols=range(1),
        )
        Eqbenchmark = np.loadtxt(
            open(os.path.join(dataFileDirPath, "Eq_Benchmark.csv")),
            delimiter=",",
            usecols=range(1),
        )

        # calculate error between output and benchmark result, which below 0.01% is pass.
        aerr = np.absolute((Q - Qbenchmark) / Qbenchmark)
        qpErr = np.absolute(qp - qpbenchmark)
        epErr = np.absolute((Ep - Eqbenchmark) / Eqbenchmark)
        F0Err = np.absolute((F0 - F0benchmark) / F0benchmark)

        # Check that the accuracy of river flow model
        assert (np.max(aerr) < 0.0001).all()
        assert (np.max(qpErr) < 0.0001).all()
        assert (np.max(epErr) < 0.0001).all()
        assert (np.max(F0Err) < 0.0001).all()

        # Check that the initial conditions (2 days: today and tomorrow)
        # have been added to the db
        readings = InitialCondition.objects.all()
        assert len(readings) == 200

    def test_calculation_dbTime(self):
        """
        test the forecast times in the DB (table:'calculations_riverflowcalculationoutput')
        are as we expect.
        """
        testInfo = prepare_test_Data()  # get test data and location
        testDate = testInfo[0]  # date

        # plus time zone information
        testDate = datetime.astimezone(testDate, tz=timezone(timedelta(hours=0)))

        # check forecast times and prediction time are as we expect
        riverFlowCalculationOutputData = RiverFlowCalculationOutput.objects.all()
        for data in riverFlowCalculationOutputData:
            id = data.id
            assert data.prediction_date == testDate
            assert data.forecast_time == testDate + timedelta(days=(id - 1) * 0.25)
