from django.conf.urls.defaults import *
from django.contrib import admin
from django.views.generic.simple import direct_to_template
from django.views.decorators.cache import cache_page

import settings
import twothreefall.views

admin.autodiscover()

urlpatterns = patterns('',
    (r'^$', cache_page(direct_to_template, settings.CACHE_DATA_TIMEOUT), {'template': 'landing.html'}),
    url(r'^about$', direct_to_template, {'template' : 'about.html'}, name="about"),
    (r'^lastfmexplorer/', include('twothreefall.lastfmexplorer.urls')),
    (r'^status/cache/$', twothreefall.views.memcached_status),
    (r'^admin/', include(admin.site.urls)),
)

# local media content
if settings.DEV:
    from django.views.static import serve
    urlpatterns += patterns('',
        (r'^media/(?P<path>.*)$', serve, {'document_root':
            settings.MEDIA_ROOT}),
    )
