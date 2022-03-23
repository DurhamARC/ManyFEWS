from django.urls import path, re_path, register_converter

from . import views, converters

register_converter(converters.BoundingBoxUrlParameterConverter, "bbox")

urlpatterns = [
    path("", views.index, name="index"),
    path(
        "depths/<int:day>/<int:hour>/<bbox:bounding_box>",
        views.depth_predictions,
        name="depths",
    ),
    path("alerts/verify", views.verify_alert, name="verify"),
    path(
        "alerts/resend-verification/<int:id>", views.resend_verification, name="verify"
    ),
    re_path(
        r"^alerts/?((?P<action>(delete)|(edit))/(?P<id>[0-9]+))?$",
        views.alerts,
        name="alerts",
    ),
]
