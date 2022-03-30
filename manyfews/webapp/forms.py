import logging

from django.contrib import messages
from django.forms import ModelChoiceField, ModelForm, ValidationError
from leaflet.forms.fields import PolygonField
from phonenumber_field.formfields import PhoneNumberField

from .alerts import TwilioAlerts
from .models import UserAlert, UserPhoneNumber


class PhoneNumberChoiceField(ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.phone_number


class UserAlertForm(ModelForm):
    location = PolygonField()
    new_phone_number = PhoneNumberField(required=False)

    class Meta:
        model = UserAlert
        fields = ["alert_type", "phone_number", "new_phone_number", "location"]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["phone_number"] = PhoneNumberChoiceField(
            queryset=UserPhoneNumber.objects.filter(user=self.user), required=False
        )

    def clean_new_phone_number(self):
        existing_number = self.cleaned_data["phone_number"]
        if existing_number:
            return None
        else:
            new_number = self.cleaned_data["new_phone_number"]
            if not new_number:
                raise ValidationError(
                    "You must provide a new phone number or choose an existing one."
                )
            return new_number

    def save(self, commit=True):
        user_alert = super().save(commit=False)
        user_alert.user = self.user
        if not user_alert.phone_number_id:
            new_number = self.cleaned_data["new_phone_number"]
            user_phone_number, created = UserPhoneNumber.objects.get_or_create(
                user=self.user, phone_number=self.cleaned_data["new_phone_number"]
            )
            user_phone_number.save()
            user_alert.phone_number = user_phone_number

        if commit:
            user_alert.save()
            if not user_alert.verified:
                try:
                    twilio_alerts = TwilioAlerts()
                    twilio_alerts.send_verification_message(
                        str(user_alert.phone_number.phone_number),
                        channel=user_alert.alert_type,
                    )
                except Exception as e:
                    logging.error(
                        f"Error sending verification message for alert {user_alert.id} via Twilio.",
                        e,
                    )
                    raise ValidationError(
                        "Unable to verify phone number. Please check the number and try again."
                    )
        return user_alert
