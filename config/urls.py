from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import include, path
from .health import health
from crm.api.docs import docs as api_docs, schema as api_schema

urlpatterns = [path('health/', health, name='health'), path('api/docs', api_docs), path('api/docs/', api_docs, name='api_docs'), path('api/schema/', api_schema, name='api_schema'), path('api/v1/', include('crm.api.urls')), path('admin/', admin.site.urls), path('login/', auth.LoginView.as_view(), name='login'), path('logout/', auth.LogoutView.as_view(), name='logout'), path('', include('crm.urls'))]
