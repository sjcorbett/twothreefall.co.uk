from django.conf.urls.defaults import *
from django.contrib import admin
from django.contrib.sitemaps import Sitemap
from django.views.generic import TemplateView
from django.views.decorators.cache import cache_page
from django.core.urlresolvers import reverse

import settings
import twothreefall.views
import lastfmexplorer.urls

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
    'lastfmexplorer': lastfmexplorer.urls.LastfmExplorerSitemap
}

admin.autodiscover()
(r'^about/', TemplateView.as_view(template_name="about.html")),

urlpatterns = patterns('',
    url(r'^$', cache_page(settings.CACHE_DATA_TIMEOUT)(TemplateView.as_view(template_name="landing.html")), name="home"),
    url(r'^about$', cache_page(settings.CACHE_DATA_TIMEOUT)(TemplateView.as_view(template_name="about.html")), name="about"),
    (r'^lastfmexplorer/', include('lastfmexplorer.urls')),
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
