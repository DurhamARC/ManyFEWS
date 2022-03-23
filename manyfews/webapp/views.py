from datetime import date, timedelta
import logging
import random

from django.conf import settings
from django.forms import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.template import loader
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from calculations.models import AggregatedDepthPrediction
from .alerts import TwilioAlerts
from .forms import UserAlertForm
from .models import UserAlert, UserPhoneNumber


MESSAGE_TAGS = {
    messages.ERROR: "danger",
}


def index(request):
    # Prepare data for the home page
    template = loader.get_template("webapp/index.html")
    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    daily_risks = []

    # Currently we generate random data; this will eventually be calculated
    # from the flood risk levels in the DB
    risk = random.randint(0, 100)
    for i in range(10):
        six_hour_risks = []
        for j in range(4):
            risk += random.randint(-10, 10)
            if risk < 0:
                risk = 0
            if risk > 100:
                risk = 100
            risk_level = 0
            if risk > 75:
                risk_level = 4
            elif risk > 50:
                risk_level = 3
            elif risk > 25:
                risk_level = 2
            elif risk > 0:
                risk_level = 1

            six_hour_risks.append(
                {"hour": j * 6, "risk_percentage": risk, "risk_level": risk_level}
            )

        daily_risks.append(
            {
                "day_number": i,
                "date": today + timedelta(days=i),
                "risks": six_hour_risks,
            }
        )

    return HttpResponse(
        template.render(
            {"daily_risks": daily_risks, "mapApiKey": settings.MAP_API_TOKEN}, request
        )
    )


def depth_predictions(request, day, hour, bounding_box):
    # Get the depth predictions for this bounding box and day days ahead
    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    predictions = AggregatedDepthPrediction.objects.filter(
        prediction_date=today + timedelta(days=day, hours=hour),
        bounding_box__intersects=bounding_box,
    )
    items = []
    for p in predictions:
        bb_extent = p.bounding_box.extent
        items.append(
            {
                "bounds": [[bb_extent[0], bb_extent[1]], [bb_extent[2], bb_extent[3]]],
                "depth": p.median_depth,
                "lower_centile": p.lower_centile,
                "upper_centile": p.upper_centile,
            }
        )
    return JsonResponse({"items": items, "max_depth": 1})


@login_required
def alerts(request, action=None, id=None):
    current_alert = None
    edit_mode = False
    if request.method == "POST":
        if id:
            current_alert = UserAlert.objects.get(user=request.user, id=id)
        form = UserAlertForm(request.POST, user=request.user, instance=current_alert)
        if form.is_valid():
            try:
                form.save()
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    "Alert added. Please check your messages to verify it.",
                )
                # Redirect to /alerts if successful
                return redirect("alerts")
            except ValidationError as e:
                messages.add_message(
                    request, messages.ERROR, e.message, extra_tags="danger"
                )
        else:
            edit_mode = True

    else:
        if id and action in ("edit", "delete"):
            current_alert = UserAlert.objects.get(user=request.user, id=id)

        if current_alert:
            if action == "edit":
                form = UserAlertForm(user=request.user, instance=current_alert)
                edit_mode = True
            elif action == "delete":
                current_alert.delete()
                return redirect("alerts")
        else:
            form = UserAlertForm(user=request.user)

    alert_objs = UserAlert.objects.filter(user=request.user).all()
    alerts = [
        {
            "id": a.id,
            "alert_type": a.get_alert_type_display(),
            "phone_number": a.phone_number,
            "verified": a.verified,
        }
        for a in alert_objs
    ]

    if form.errors.get("location"):
        form.errors["location"][0] += " Use the toolbox to select an area on the map."

    template = loader.get_template("webapp/alerts.html")
    return HttpResponse(
        template.render(
            {
                "form": form,
                "mapApiKey": settings.MAP_API_TOKEN,
                "alerts": alerts,
                "edit": edit_mode,
            },
            request,
        )
    )


@login_required
def verify_alert(request):
    try:
        id = int(request.POST.get("alert_id"))
        code = request.POST.get("verification_code")
        if id and code:
            user_alert = UserAlert.objects.get(user=request.user, id=id)
            twilio_alerts = TwilioAlerts()
            verified = twilio_alerts.check_verification_code(
                str(user_alert.phone_number.phone_number), code
            )
            if verified:
                user_alert.verified = True
                user_alert.save()
                messages.add_message(
                    request, messages.SUCCESS, "Verification succeeded."
                )
            else:
                messages.add_message(
                    request,
                    messages.ERROR,
                    "Verification failed. Please try again.",
                    extra_tags="danger",
                )
    except Exception as e:
        logging.error(
            f"Error when verifying message for alert {user_alert.id} via Twilio.", e
        )
        messages.add_message(
            request,
            messages.ERROR,
            "Verification failed. Please try again.",
            extra_tags="danger",
        )

    # Redirect to /alerts
    return redirect("alerts")


@login_required
def resend_verification(request, id):
    try:
        user_alert = UserAlert.objects.get(user=request.user, id=id)
        twilio_alerts = TwilioAlerts()
        verification_sent = twilio_alerts.send_verification_message(
            str(user_alert.phone_number.phone_number), user_alert.alert_type
        )
        if verification_sent:
            messages.add_message(
                request,
                messages.INFO,
                f"We have sent a verification code to {str(user_alert.phone_number.phone_number)}. Use the 'Verify' button to enter the code to verify your alert.",
            )
        else:
            messages.add_message(
                request,
                messages.ERROR,
                f"Unable to send verification code to {str(user_alert.phone_number.phone_number)}. Please check the number and try again.",
                extra_tags="danger",
            )
    except Exception as e:
        logging.error(
            f"Error sending verification for alert {user_alert.id} via Twilio. %s", e
        )
        messages.add_message(
            request,
            messages.ERROR,
            f"Unable to send verification code to {str(user_alert.phone_number.phone_number)}. Please check the number and try again.",
            extra_tags="danger",
        )

    # Redirect to /alerts
    return redirect("alerts")
