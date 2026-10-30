from django.contrib import admin
from django.urls import include, path

from accounts.views import index


urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/index", index, name="index"),
    path("api/index/", index, name="index"),
    path("", include("accounts.urls")),
]
