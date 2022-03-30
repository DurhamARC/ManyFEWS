from django.conf import settings
from django.contrib.gis.db.models import Max, Min, Union
from django.utils import timezone

from webapp.alerts import TwilioAlerts
from webapp.models import UserAlert, UserPhoneNumber, AlertType

from .models import AggregatedDepthPrediction

import logging

logger = logging.getLogger(__name__)


def send_phone_alerts_for_user(user_id, phone_number_id, alert_type=AlertType.SMS):
    """Send alerts to a user's phone number, i.e. via WhatsApp or SMS"""
    user_sms_alerts = (
        UserAlert.objects.filter(
            user_id=user_id, phone_number_id=phone_number_id, alert_type=alert_type
        )
        .values("user", "phone_number")
        .annotate(all_locations=Union("location"))
    )

    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    five_days_ahead = today + timezone.timedelta(days=5)
    twilio_alerts = TwilioAlerts()

    for alert in user_sms_alerts:
        try:
            message = get_message(today, five_days_ahead, alert["all_locations"])
            if message:
                phone_number = str(
                    UserPhoneNumber.objects.get(id=alert["phone_number"]).phone_number
                )
                if alert_type == AlertType.SMS:
                    twilio_alerts.send_alert_sms(phone_number, message)
                else:
                    twilio_alerts.send_alert_whatsapp(phone_number, message)
        except Exception as e:
            logger.error(
                f"Unable to send message for phone number id {alert['phone_number']}: {e}"
            )


def get_message(start_date, end_date, location):
    # Find values in AggregatedDepthPrediction in future which match this area
    predictions = AggregatedDepthPrediction.objects.filter(
        prediction_date__gte=start_date,
        prediction_date__lte=end_date,
        bounding_box__intersects=location,
        median_depth__gte=settings.ALERT_DEPTH_THRESHOLD,  # FIXME once changes merged
    ).aggregate(Min("prediction_date"), Max("prediction_date"), Max("median_depth"))
    if predictions["median_depth__max"]:
        return settings.ALERT_TEXT.format(
            max_depth=f"{predictions['median_depth__max']:.1f}",
            start_date=predictions["prediction_date__min"].strftime(
                settings.ALERT_DATE_FORMAT
            ),
            end_date=predictions["prediction_date__max"].strftime(
                settings.ALERT_DATE_FORMAT
            ),
            site_url=settings.SITE_URL,
        )
    else:
        return None
