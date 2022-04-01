from datetime import datetime, timedelta, timezone
import os
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.gis.geos import Point, Polygon
from django.test import TestCase
import numpy as np
import xlrd

from webapp.models import UserAlert, UserPhoneNumber, AlertType
from .alerts import send_phone_alerts_for_user
from .flood_risk_aggregation import predict_aggregated_depth
from .models import (
    AggregatedDepthPrediction,
    FloodModelParameters,
    ZentraDevice,
    ZentraReading,
    NoaaForecast,
    InitialCondition,
    RiverFlowCalculationOutput,
    RiverFlowPrediction,
)
from .tasks import prepareZentra, prepareGEFS, runningGenerateRiverFlows, send_alerts


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
        assert len(readings) == 8


class ModelCalculationTests(TestCase):
    def test_calculation_GenerateRiverFlow(self):
        testInfo = prepare_test_Data()  # get test data and location
        testDate = testInfo[0]  # date
        testLocation = testInfo[1]  # location

        # plus time zone information
        testDate = datetime.astimezone(testDate, tz=timezone(timedelta(hours=0)))
        nextDay = testDate + timedelta(days=1)
        runningGenerateRiverFlows(
            dt=0.25, predictionDate=testDate, dataLocation=testLocation
        )

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
            open(os.path.join(dataFileDirPath, "F0_Benchmark.csv")),
            usecols=range(3),
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


class UserAlertTests(TestCase):
    def setUpAlerts(self):
        # Add some user alerts to db
        self.user = User(username="user1")
        self.user.save()
        self.phone_number1 = UserPhoneNumber(
            user=self.user, phone_number="+441234567890"
        )
        self.phone_number1.save()
        self.phone_number2 = UserPhoneNumber(
            user=self.user, phone_number="+449876543210"
        )
        self.phone_number2.save()
        self.alert1 = UserAlert(
            user=self.user,
            phone_number=self.phone_number1,
            alert_type=AlertType.SMS,
            location=Polygon.from_bbox((0, 0, 10, 10)),
        )
        self.alert1.save()
        self.alert2 = UserAlert(
            user=self.user,
            phone_number=self.phone_number1,
            alert_type=AlertType.SMS,
            location=Polygon.from_bbox((0, 10, 10, 20)),
        )
        self.alert2.save()
        self.alert3 = UserAlert(
            user=self.user,
            phone_number=self.phone_number2,
            alert_type=AlertType.SMS,
            location=Polygon.from_bbox((10, 10, 20, 20)),
        )
        self.alert3.save()

    @mock.patch("calculations.tasks.send_user_sms_alerts")
    def test_send_alerts(self, mock):
        # Call send_alerts: mock should not be called as nothing in db
        send_alerts()
        mock.assert_not_called()

        self.setUpAlerts()

        # Call send_alerts again. Should not call mock as alerts not verified.
        send_alerts()
        mock.assert_not_called()

        # Verify alerts 1 and 2
        self.alert1.verified = True
        self.alert1.save()
        self.alert2.verified = True
        self.alert2.save()

        # Call send_alerts again. Should call mock delay with user and phone number1 ids
        send_alerts()
        mock.delay.assert_called_once_with(self.user.id, self.phone_number1.id)

        mock.reset_mock()

        # Verify alert 3
        self.alert3.verified = True
        self.alert3.save()
        # Call send_alerts again. Should call mock delay twice with both phone numbers
        send_alerts()
        mock.delay.assert_has_calls(
            mock.call(self.user.id, self.phone_number1.id),
            mock.call(self.user.id, self.phone_number2.id),
        )

    @mock.patch("calculations.alerts.TwilioAlerts.send_alert_sms")
    def test_send_sms_alerts(self, sms_mock):
        self.setUpAlerts()
        # No depths in db so should not make any calls to Twilio apart from constructor
        send_phone_alerts_for_user(1, 1)
        sms_mock.assert_not_called()

        # Add an AggregatedDepthPrediction in a location crossing alert2 and alert3
        prediction = AggregatedDepthPrediction(
            date=datetime.utcnow().date() + timedelta(days=1),
            bounding_box=Polygon.from_bbox((9, 9, 11, 11)),
            median_depth=1,
            lower_centile=0.5,
            mid_lower_centile=0.7,
            upper_centile=1.5,
        )
        prediction.save()

        # Call with user 1, phone number 1
        send_phone_alerts_for_user(self.user.id, self.phone_number1.id)
        assert sms_mock.call_count == 1
        call_args = sms_mock.call_args[0]
        assert call_args[0] == "+441234567890"
        assert call_args[1].startswith("Floods up to 1.0m predicted from ")
        assert call_args[1].endswith("See http://localhost:8000 for details.")

        sms_mock.reset_mock()

        # Call with user 1, phone number 2
        send_phone_alerts_for_user(self.user.id, self.phone_number2.id)
        assert sms_mock.call_count == 1
        call_args2 = sms_mock.call_args[0]
        assert call_args2[0] == "+449876543210"
        assert call_args2[1] == call_args[1]


class FloodCalculationTests(TestCase):
    def test_predict_aggregated_depth(self):
        date = datetime.utcnow().date()
        params = [1, 2, 3]
        param = FloodModelParameters(beta0=1, beta1=2, beta2=3)
        vals = np.array([[4, 5], [6, 7], [8, 9]])
        stats = predict_aggregated_depth(vals, param)
        assert stats == (26.0, 30.0, 34.0, 42.0)

        vals = np.array([10, 20, 30, 40])
        stats = predict_aggregated_depth(vals, param)
        assert stats == (16.0, 22.0, 28.0, 40.0)
