from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import include, path
from .health import health

urlpatterns = [path('health/', health, name='health'), path('admin/', admin.site.urls), path('login/', auth.LoginView.as_view(), name='login'), path('logout/', auth.LogoutView.as_view(), name='logout'), path('', include('crm.urls'))]
