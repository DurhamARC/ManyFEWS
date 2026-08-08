from datetime import datetime, timedelta, timezone
import os, tempfile

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import TestCase
import numpy as np
from unittest import mock

from webapp.models import UserAlert, UserPhoneNumber, AlertType
from .alerts import send_phone_alerts_for_user
from .flood_risk import predict_depth, predict_depths
from .models import (
    DepthPrediction,
    FloodModelParameters,
    ModelVersion,
    RiverChannel,
    NoaaForecast,
    InitialCondition,
    AggregatedWeatherReading,
    RiverFlowPrediction,
    RiverFlowCalculationOutput,
)
from .tasks import (
    initialModelSetUp,
    dailyModelUpdate,
    send_alerts,
    load_params_from_csv,
)
from .open_meteo import offsetTime


class _FakeOpenMeteoResponse:
    """A minimal stand-in for requests.Response, for mocking Open-Meteo calls."""

    def __init__(self, json_data):
        self._json_data = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data


def _synthetic_hourly(start_date_str, end_date_str, member_suffixes=("",)):
    """
    Build a synthetic Open-Meteo "hourly" response dict covering
    [start_date, end_date] inclusive (24 hourly points/day, UTC), for one or
    more ensemble member suffixes (e.g. ("", "_member01", ...)).
    """
    start = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(end_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    num_hours = ((end.date() - start.date()).days + 1) * 24

    times = [int((start + timedelta(hours=h)).timestamp()) for h in range(num_hours)]

    hourly = {"time": times}
    for suffix in member_suffixes:
        hourly[f"precipitation{suffix}"] = [0.1] * num_hours
        hourly[f"temperature_2m{suffix}"] = [
            20.0 + (h % 24) * 0.1 for h in range(num_hours)
        ]
        hourly[f"windspeed_10m{suffix}"] = [5.0] * num_hours
        hourly[f"winddirection_10m{suffix}"] = [180.0] * num_hours
        hourly[f"relativehumidity_2m{suffix}"] = [70.0] * num_hours

    return {"hourly": hourly}


def _mock_open_meteo_get(url, params=None, timeout=None):
    """
    Stand-in for calculations.open_meteo.requests.get, used to test the
    Open-Meteo integration without hitting the network. Returns synthetic
    hourly data spanning exactly the requested date range, so
    prepareOpenMeteoHistorical's completeness check passes and
    prepareOpenMeteo produces a predictable number of ensemble members.
    """
    start_date = params["start_date"]
    end_date = params["end_date"]

    if "archive-api" in url:
        return _FakeOpenMeteoResponse(_synthetic_hourly(start_date, end_date))

    # Ensemble forecast endpoint: return more members than
    # OPEN_METEO_ENSEMBLE_MEMBERS so the truncation logic gets exercised.
    member_suffixes = ("", "_member01", "_member02", "_member03", "_member04")
    return _FakeOpenMeteoResponse(
        _synthetic_hourly(start_date, end_date, member_suffixes=member_suffixes)
    )


class TaskTest(TestCase):
    @mock.patch(
        "calculations.open_meteo.requests.get", side_effect=_mock_open_meteo_get
    )
    def test_initial_model_setup(self, mock_get):
        """
        Test the initial Model SetUp and daily update tasks.
        """

        # test initial model setup task.
        initialModelSetUp()

        # Check that there are historical weather readings in the database,
        # covering INITIAL_BACKTIME days (4 six-hour buckets/day).
        location = Point(settings.LON_VALUE, settings.LAT_VALUE)
        self.timeInfo = offsetTime(backDays=settings.INITIAL_BACKTIME)
        self.startTime = self.timeInfo[0]
        self.endTime = self.timeInfo[1] + timedelta(days=settings.INITIAL_BACKTIME)

        self.aggregateReading = AggregatedWeatherReading.objects.filter(
            date__range=(self.startTime, self.endTime)
        ).filter(location=location)

        assert len(self.aggregateReading) == settings.INITIAL_BACKTIME * 4

        # check that there are initial conditions in the database
        self.initial_condition = InitialCondition.objects.all()
        assert len(self.initial_condition) == 100

        # test daily model update task.
        dailyModelUpdate()

        # Open-Meteo ensemble forecast: OPEN_METEO_ENSEMBLE_MEMBERS members,
        # each with OPEN_METEO_FORECAST_DAYS * 4 six-hour buckets.
        num_members = settings.OPEN_METEO_ENSEMBLE_MEMBERS
        buckets_per_member = settings.OPEN_METEO_FORECAST_DAYS * 4

        self.forecastReadings = NoaaForecast.objects.all()
        assert len(self.forecastReadings) == num_members * buckets_per_member

        # every member gets a saved river flow forecast (riverFlowSave=True)...
        self.riverOutput = RiverFlowCalculationOutput.objects.all()
        assert len(self.riverOutput) == num_members * buckets_per_member

        self.riverOutputPrediction = RiverFlowPrediction.objects.all()
        assert len(self.riverOutputPrediction) == num_members * buckets_per_member * 100

        # ...but only the control member's state carries forward, so only
        # 100 more InitialCondition rows get added (not num_members * 100).
        self.initialCondition = InitialCondition.objects.all()
        assert len(self.initialCondition) == 200

    def test_load_params_from_csv(self):
        self.csv = (
            "lng,lat,size,P0,P1,P2,P3,minQ\n"
            "100.0,1.0,1.8E-05,-0.7,0.01,-1.17E-05,4.56E-09,125\n"
            "100.0,1.0,1.8E-05,-0.7,0.01,1.07E-05,-2.93E-08,125\n"
            "100.0,1.0,1.8E-05,-0.7,0.01,-2.46E-05,2.50E-08,125\n"
            "100.0,1.0,1.8E-05,-0.7,0.01,-3.71E-05,4.37E-08,100\n"
            "100.0,1.0,1.8E-05,-0.7,0.01,-4.50E-05,5.54E-08,100\n"
            "100.0,1.0,1.8E-05,-0.7,0.01,-3.29E-05,3.62E-08,100\n"
            "100.0,1.0,1.8E-05,-0.7,0.01,-2.76E-05,2.69E-08,100\n"
            "100.0,1.0,1.8E-05,-0.7,0.01,-2.15E-05,1.76E-08,100\n"
            "100.0,1.0,1.8E-05,-0.7,0.01,-4.03E-05,4.71E-08,100"
        )

        self.csv = self.csv.encode("utf-8")

        self.version_name = "1"
        self.model_version = ModelVersion(
            version_name=self.version_name, is_current=True
        )
        self.model_version.save()

        assert ModelVersion.objects.first().version_name == self.version_name

        settings.DATABASE_CHUNK_SIZE = 5

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            # logging.info(f"Creating temporary file: {tmp.name}")
            try:
                tmp.write(self.csv)
            finally:
                tmp.close()
                load_params_from_csv(
                    filename=tmp.name, model_version_id=self.version_name
                )
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
        with self.assertNumQueries(4):
            predict_depths(self.test_date, dummy_param_list, None)

        self.assertEqual(DepthPrediction.objects.filter(date=self.test_date).count(), 0)

    @mock.patch("calculations.flood_risk.predict_depth")
    def test_bulk_predict_depths_create(self, predict_depth):
        predict_depth.return_value = (8.14, 21.95, 36.63, 1)

        dummy_param_list = [1, 2, 3, 4]

        self.assertEqual(DepthPrediction.objects.filter(date=self.test_date).count(), 0)
        with self.assertNumQueries(8):
            predict_depths(self.test_date, dummy_param_list, None)

        self.assertEqual(DepthPrediction.objects.filter(date=self.test_date).count(), 4)

    @mock.patch("calculations.flood_risk.predict_depth")
    def test_bulk_predict_depths_update(self, predict_depth):
        predict_depth.return_value = (8.14, 21.95, 36.63, 1)
        self.create_depth_predictions()

        dummy_param_list = [1, 2, 3, 4]

        self.assertEqual(DepthPrediction.objects.filter(date=self.test_date).count(), 4)
        with self.assertNumQueries(8):
            predict_depths(self.test_date, dummy_param_list, None)

        self.assertEqual(DepthPrediction.objects.filter(date=self.test_date).count(), 4)
