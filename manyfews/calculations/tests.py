from datetime import datetime, timedelta, timezone
import os, tempfile

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import TestCase
import numpy as np
import xlrd
from unittest import mock

from webapp.models import UserAlert, UserPhoneNumber, AlertType
from .alerts import send_phone_alerts_for_user
from .flood_risk import predict_depth, predict_depths
from .models import (
    DepthPrediction,
    FloodModelParameters,
    ModelVersion,
    RiverChannel,
    ZentraDevice,
    ZentraReading,
    NoaaForecast,
    InitialCondition,
    AggregatedZentraReading,
    RiverFlowPrediction,
    RiverFlowCalculationOutput,
)
from .tasks import (
    initialModelSetUp,
    dailyModelUpdate,
    send_alerts,
    load_params_from_csv,
    import_zentra_devices,
)
from .zentra import offsetTime


def excel_to_matrix(path, sheet_num):
    """
    This function is used to convert data form from excel (.xlsx) into a Numpy array.

    :param path: the absolute path of the excel file.
    :param sheet_num: the sheet number of the table in the excel file.

    """

    table = xlrd.open_workbook(path).sheets()[sheet_num]
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


def prepare_test_data():
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


class TaskTest(TestCase):
    def test_tasks(self):
        #  Check the initialModelSetUp task can run and adds some records to the db
        self.sn = "06-02047"
        zentraDevice = ZentraDevice(self.sn, location=Point(0, 0))
        zentraDevice.save()

        self.test_load_params_from_csv()
        self.test_initial_model_setup()
        self.test_daily_model_update()
        self.test_import_zentra_devices()

    def test_import_zentra_devices(self):
        import_zentra_devices()

    def test_initial_model_setup(self):
        """
        Test the initial Model SetUp and daily update tasks.
        """

        # test initial model setup task.
        initialModelSetUp()

        # Check that there are readings (past 365 days) in the database

        self.timeInfo = offsetTime(backDays=365)
        self.startTime = self.timeInfo[0]
        self.endTime = self.timeInfo[1] + timedelta(days=365)

        self.readings = ZentraReading.objects.filter(
            date__range=(self.startTime, self.endTime)
        )
        self.aggregateReading = AggregatedZentraReading.objects.filter(
            date__range=(self.startTime, self.endTime)
        )

        assert len(self.readings) == 1440
        assert len(self.aggregateReading) == 20

        # check that there are initial conditions in the database
        self.initial_condition = InitialCondition.objects.all()
        assert len(self.initial_condition) == 100

    def test_daily_model_update(self):
        # test daily model update task.
        dailyModelUpdate()

        # check that there are output in the database
        self.riverOutput = RiverFlowCalculationOutput.objects.all()
        assert len(self.riverOutput) == 8

        self.riverOutputPrediction = RiverFlowPrediction.objects.all()
        assert len(self.riverOutputPrediction) == 800

        # check that the new initial condition in the database
        self.initialCondition = InitialCondition.objects.all()
        assert len(self.initialCondition) == 200

        # check the gefs data
        self.gefsReadings = NoaaForecast.objects.all()
        assert len(self.gefsReadings) == 8

    def test_load_params_from_csv(self):
        self.csv = """lng,lat,size,P0,P1,P2,P3,minQ
100.0,1.0,1.8E-05,-0.7,0.01,-1.17E-05,4.56E-09,125
100.0,1.0,1.8E-05,-0.7,0.01,1.07E-05,-2.93E-08,125
100.0,1.0,1.8E-05,-0.7,0.01,-2.46E-05,2.50E-08,125
100.0,1.0,1.8E-05,-0.7,0.01,-3.71E-05,4.37E-08,100
100.0,1.0,1.8E-05,-0.7,0.01,-4.50E-05,5.54E-08,100
100.0,1.0,1.8E-05,-0.7,0.01,-3.29E-05,3.62E-08,100
100.0,1.0,1.8E-05,-0.7,0.01,-2.76E-05,2.69E-08,100
100.0,1.0,1.8E-05,-0.7,0.01,-2.15E-05,1.76E-08,100
100.0,1.0,1.8E-05,-0.7,0.01,-4.03E-05,4.71E-08,100
        """

        settings.DATABASE_CHUNK_SIZE = 5

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            # logging.info(f"Creating temporary file: {tmp.name}")
            try:
                tmp.write(self.csv)
            finally:
                tmp.close()
                load_params_from_csv(self, tmp.name, -1)
                os.unlink(tmp.name)


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

        # Add an DepthPrediction in a location crossing alert2 and alert3
        model_version = ModelVersion(version_name="v1", is_current=True)
        model_version.save()
        parameters = FloodModelParameters(
            model_version=model_version,
            bounding_box=Polygon.from_bbox((9, 9, 11, 11)),
            beta0=0,
        )
        parameters.save()
        prediction = DepthPrediction(
            date=datetime.utcnow().date() + timedelta(days=1),
            parameters=parameters,
            median_depth=1,
            lower_centile=0.5,
            mid_lower_centile=0.7,
            upper_centile=1.5,
            model_version=model_version,
        )
        prediction.save()

        # Call with user 1, phone number 1
        send_phone_alerts_for_user(self.user.id, self.phone_number1.id)
        assert sms_mock.call_count == 1
        call_args = sms_mock.call_args[0]
        assert call_args[0] == "+441234567890"
        assert call_args[1].startswith("Floods up to 1.0m predicted from ")
        assert call_args[1].endswith(f"See {settings.SITE_URL} for details.")

        sms_mock.reset_mock()

        # Call with user 1, phone number 2
        send_phone_alerts_for_user(self.user.id, self.phone_number2.id)
        assert sms_mock.call_count == 1
        call_args2 = sms_mock.call_args[0]
        assert call_args2[0] == "+449876543210"
        assert call_args2[1] == call_args[1]

        sms_mock.reset_mock()

        # Add a RiverChannel which covers all of the depth prediction - should not send alert
        channel = RiverChannel(
            channel_location=MultiPolygon([Polygon.from_bbox((8, 8, 12, 12))])
        )
        channel.save()
        send_phone_alerts_for_user(self.user.id, self.phone_number2.id)
        assert sms_mock.call_count == 0

        sms_mock.reset_mock()

        # Modify river channel so it only covers part of the DepthPrediction and alert intersection - should send alert
        channel.channel_location = MultiPolygon(
            [Polygon.from_bbox((10, 10, 10.5, 10.5))]
        )
        channel.save()
        send_phone_alerts_for_user(self.user.id, self.phone_number2.id)
        assert sms_mock.call_count == 1
        call_args2 = sms_mock.call_args[0]
        assert call_args2[0] == "+449876543210"
        assert call_args2[1] == call_args[1]


class FloodCalculationTests(TestCase):
    fixtures = ["ModelVersion", "FloodModelParameters"]

    def setUp(self):
        super().setUp()
        self.test_date = datetime(2015, 10, 3, 23, 55, 59, 342380)

    def create_depth_predictions(self):
        model_version = ModelVersion.objects.first()

        depth_predictions = [
            DepthPrediction.objects.create(
                date=self.test_date,
                parameters_id=param_id,
                lower_centile=0.5,
                median_depth=1,
                mid_lower_centile=0.7,
                upper_centile=1.5,
                model_version=model_version,
            )
            for param_id in range(1, 5)
        ]

    def test_predict_depth(self):
        params = FloodModelParameters(beta0=1, beta1=2, beta2=3, beta3=4)

        # Test with all the same flows so centiles and medians will be actual value
        flows = np.array([2, 2, 2, 2])
        stats = predict_depth(flows, params)
        assert stats == (49, 49, 49, 49)

        # Test with different flows
        flows = np.array([0.1, 2, 1.5, 5])
        stats = predict_depth(flows, params)
        np.testing.assert_almost_equal(stats, (8.14, 21.95, 36.63, 424.90), 2)

        # Test values below 0 are set to 0
        params = FloodModelParameters(beta0=-1, beta1=-2, beta2=-3, beta3=-4)
        flows = np.array([0.1, 2, 1.5, 5])
        stats = predict_depth(flows, params)
        assert stats == (0, 0, 0, 0)

    @mock.patch("calculations.flood_risk.predict_depth")
    def test_bulk_predict_depths_delete(self, predict_depth):
        predict_depth.return_value = (8.14, 21.95, 36.63, -1)
        dummy_param_list = [1, 2, 3, 4]
        self.create_depth_predictions()

        self.assertEqual(DepthPrediction.objects.filter(date=self.test_date).count(), 4)
        with self.assertNumQueries(6):
            predict_depths(self.test_date, dummy_param_list, None)

        self.assertEqual(DepthPrediction.objects.filter(date=self.test_date).count(), 0)

    @mock.patch("calculations.flood_risk.predict_depth")
    def test_bulk_predict_depths_create(self, predict_depth):
        predict_depth.return_value = (8.14, 21.95, 36.63, 1)

        dummy_param_list = [1, 2, 3, 4]

        self.assertEqual(DepthPrediction.objects.filter(date=self.test_date).count(), 0)
        with self.assertNumQueries(10):
            predict_depths(self.test_date, dummy_param_list, None)

        self.assertEqual(DepthPrediction.objects.filter(date=self.test_date).count(), 4)

    @mock.patch("calculations.flood_risk.predict_depth")
    def test_bulk_predict_depths_update(self, predict_depth):
        predict_depth.return_value = (8.14, 21.95, 36.63, 1)
        self.create_depth_predictions()

        dummy_param_list = [1, 2, 3, 4]

        self.assertEqual(DepthPrediction.objects.filter(date=self.test_date).count(), 4)
        with self.assertNumQueries(10):
            predict_depths(self.test_date, dummy_param_list, None)

        self.assertEqual(DepthPrediction.objects.filter(date=self.test_date).count(), 4)
