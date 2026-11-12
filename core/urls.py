from django.urls import path
from . import views
app_name = 'core'
urlpatterns = [
    path('', views.home, name='home'),
    path('healthz/', views.health, name='health'),
    path('manage/', views.manager, name='manager'),
    path('manage/announcements/', views.announcements, name='announcements'),
    path('manage/announcements/<int:pk>/', views.announcements, name='announcement_edit'),
]
