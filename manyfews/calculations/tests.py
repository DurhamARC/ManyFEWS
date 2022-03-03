from django.contrib.gis.geos import Point
from django.test import TestCase

# Create your tests here.
from .models import ZentraDevice, ZentraReading, NoaaForecast, InitialCondition
from .tasks import prepareZentra, prepareGEFS, runningGenerateRiverFlows
from .GenerateRiverFlows import prepare_test_Data
from django.test import TestCase
import numpy as np
import os


class WeatherImportTests(TestCase):
    def test_fetch_from_zentra(self):
        # Check that the prepareZentra task can run and adds some records to the db
        sn = "06-02047"
        zentraDevice = ZentraDevice(sn, location=Point(0, 0))
        zentraDevice.save()

        prepareZentra()

        # Check that there are readings in the database
        readings = ZentraReading.objects.all()
        assert len(readings) > 100

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
        riverFlowsData = runningGenerateRiverFlows(
            dataDate=testDate, dataLocation=testLocation
        )

        # extract output of river flows model.
        Q = riverFlowsData[0]
        qp = riverFlowsData[1]
        Ep = riverFlowsData[2]
        F0 = riverFlowsData[3]

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
