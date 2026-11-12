from django.urls import path
from . import views

app_name = "wiki"
urlpatterns = [
    path("", views.search, name="search"),
    path("manage/", views.manage, name="manage"),
    path("manage/new/", views.new_document, name="new"),
    path("manage/<int:pk>/", views.edit, name="edit"),
    path("manage/<int:pk>/publish/", views.publish, name="publish"),
    path("manage/<int:pk>/archive/", views.archive, name="archive"),
    path("manage/document/<int:pk>/revise/", views.revise, name="revise"),
]
