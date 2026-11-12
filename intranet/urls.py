from django.contrib.auth import views as auth_views
from django.urls import include, path
from core.views import DemoRoleLoginView

urlpatterns = [
    path('login/', DemoRoleLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('core.urls')),
    path('wiki/', include('wiki.urls')),
    path('', include('operations.urls')),
]
