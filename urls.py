from django.conf.urls.defaults import *
from django.contrib import admin
from django.contrib.sitemaps import Sitemap
from django.views.generic.simple import direct_to_template
from django.views.decorators.cache import cache_page
from django.core.urlresolvers import reverse

import settings
import twothreefall.views
import twothreefall.lastfmexplorer.urls

# Includes named views in sitemap
class ViewSitemap(Sitemap):
    """Reverse static views for XML sitemap."""
    def items(self):
        # Return list of url names for views to include in sitemap
        return ['home', 'about']

    def location(self, item):
        return reverse(item)

sitemaps = {
    'views': ViewSitemap,
    'lastfmexplorer': twothreefall.lastfmexplorer.urls.LastfmExplorerSitemap
}

admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', cache_page(direct_to_template, settings.CACHE_DATA_TIMEOUT), {'template': 'landing.html'}, name="home"),
    url(r'^about$', cache_page(direct_to_template, settings.CACHE_DATA_TIMEOUT), {'template' : 'about.html'}, name="about"),
    (r'^lastfmexplorer/', include('twothreefall.lastfmexplorer.urls')),
    (r'^status/cache/$', twothreefall.views.memcached_status),
    (r'^admin/', include(admin.site.urls)),
    (r'^sitemap\.xml$', 'django.contrib.sitemaps.views.sitemap', {'sitemaps': sitemaps})
)

# local media content
if settings.DEV:
    from django.views.static import serve
    urlpatterns += patterns('',
        (r'^media/(?P<path>.*)$', serve, {'document_root':
            settings.MEDIA_ROOT}),
    )
