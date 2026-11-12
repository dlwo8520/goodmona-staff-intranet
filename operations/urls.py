from django.urls import path
from . import views

app_name = "operations"
urlpatterns = [
    path("leave/", views.leave, name="leave"),
    path("leave/<int:pk>/cancel/", views.leave_cancel, name="leave_cancel"),
    path("vehicles/", views.vehicles, name="vehicles"),
    path("vehicles/<int:pk>/cancel/", views.reservation_cancel, name="reservation_cancel"),
    path("manage/leave/", views.manage, name="manage"),
    path("manage/leave/<int:pk>/process/", views.leave_process, name="leave_process"),
    path("manage/balances/", views.balances, name="balances"),
    path("manage/vehicles/", views.vehicle_manage, name="vehicle_manage"),
    path("manage/vehicles/<int:pk>/", views.vehicle_manage, name="vehicle_edit"),
]
