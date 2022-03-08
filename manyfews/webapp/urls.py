from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("depths", views.depth_predictions, name="depths"),
]
