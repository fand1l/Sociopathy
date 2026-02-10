from django.urls import path
from . import views

app_name = "relationships"

urlpatterns = [
    path("u/<str:username>/follow/", views.follow_toggle, name="follow_toggle"),
]
