from django.core.exceptions import ValidationError
from django.forms import EmailField

from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class EmailUserCreationForm(UserCreationForm):
    """
    Subclass Django's user creation form to use an email address as the username
    """

    email = EmailField(required=True)

    class Meta:
        model = User
        fields = ("email", "password1", "password2")

    def clean_email(self):
        # Ensure email address doesn't already exist
        email_address = self.cleaned_data["email"]
        if User.objects.filter(email=email_address).count():
            raise ValidationError("A user with this email address already exists.")

        return email_address

    def save(self, commit=True):
        # Save email address to username field as well
        user = super().save(commit=False)
        user.username = user.email
        if commit:
            user.save()
        return user
