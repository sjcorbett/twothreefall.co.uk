from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template
from django.views.decorators.cache import cache_page

import settings
import twothreefall.views


urlpatterns = patterns('',
    (r'^$', cache_page(direct_to_template, settings.CACHE_DATA_TIMEOUT), {'template': 'landing.html'}),
    url(r'^about$', cache_page(direct_to_template, settings.CACHE_DATA_TIMEOUT), {'template' : 'about.html'}, name="about"),

    (r'^lastfmexplorer/', include('twothreefall.lastfmexplorer.urls')),
    (r'^status/cache/$', twothreefall.views.memcached_status),

    # (r'^twothreefall/', include('twothreefall.foo.urls')),

)

# local media content and memcached stats
if settings.DEV:
    urlpatterns += patterns('',
        (r'^.*/?(media/img/.*)', twothreefall.views.load_image),
        (r'^.*media/style.css', twothreefall.views.stylesheet),
        (r'^.*/?media/js/([\w\d./-]*)$', twothreefall.views.javascript))

