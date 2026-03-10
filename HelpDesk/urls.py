from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse


def favicon_view(_request):
    # Return "No Content" so browsers stop generating noisy 404s.
    return HttpResponse(status=204)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("myapp.urls")),
    path("favicon.ico", favicon_view, name="favicon"),
]

if settings.DEBUG or getattr(settings, "IS_RUNSERVER", False):
    urlpatterns += static(settings.MEDIA_URL,  document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

admin.site.site_header = "Helpdesk Administration"
admin.site.site_title  = "Helpdesk Admin Portal"
admin.site.index_title = "Welcome to Helpdesk Admin Panel"

