from django.contrib import admin
from django.conf.urls.static import static
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('accounts/', include('accounts.urls')),
    path('chats/', include('chats.urls')),
    path('orders/', include('orders.urls')),
    path('comments/', include('comments.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += [
        re_path(
            r'^publication-files/(?P<path>.*)$',
            serve,
            {'document_root': settings.PUBLICATION_STORAGE_ROOT},
        ),
    ]
