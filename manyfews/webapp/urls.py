from django.urls import path, register_converter

from . import views, converters

register_converter(converters.BoundingBoxUrlParameterConverter, "bbox")

urlpatterns = [
    path("", views.index, name="index"),
    path(
        "depths/<int:day>/<bbox:bounding_box>", views.depth_predictions, name="depths"
    ),
]
