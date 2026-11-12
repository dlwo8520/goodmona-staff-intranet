from django.urls import path
from . import views
from . import calendar_views as calendars

app_name = "operations"
urlpatterns = [
    path("leave/", calendars.leave, name="leave"),
    path("leave/<int:pk>/cancel/", views.leave_cancel, name="leave_cancel"),
    path("vehicles/", calendars.vehicles, name="vehicles"),
    path("vehicles/<int:pk>/cancel/", views.reservation_cancel, name="reservation_cancel"),
    path("manage/leave/", calendars.manage, name="manage"),
    path('api/leave/calendar/', calendars.leave_calendar, name='leave_calendar'),
    path('api/manage/leave/calendar/', calendars.manage_calendar, name='manage_calendar'),
    path('api/vehicles/calendar/', calendars.vehicle_calendar, name='vehicle_calendar'),
    path('manage/staffing/', calendars.staffing, name='staffing'),
    path('manage/leave/<int:pk>/period/', calendars.confirm_period, name='confirm_period'),
    path("manage/leave/<int:pk>/process/", views.leave_process, name="leave_process"),
    path("manage/balances/", views.balances, name="balances"),
    path("manage/vehicles/", views.vehicle_manage, name="vehicle_manage"),
    path("manage/vehicles/<int:pk>/", views.vehicle_manage, name="vehicle_edit"),
]
