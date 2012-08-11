from django.conf.urls.defaults import *
from django.contrib.sitemaps import Sitemap

import views
import ldates

from managers import USER_REGEX
from models import User

# match usernames
__user_base     = '^user/' + USER_REGEX + '/' 

# match week indexes
__date_matcher  = r'(?P<start>\d+)-(?P<end>\d+)/$'
__year_matcher  = r'(?P<year>\d{4})/$'
__default_dates = { 'start' : ldates.idx_beginning,
                    'end'   : ldates.idx_last_sunday }

urlpatterns = patterns('twothreefall.lastfmexplorer.views',
    # start
    (r'^$', 'start'),

    # updates
    (__user_base + 'update/$', 'update'),
    (r'^poll-update$', 'poll_update_status'),

    # invalid XML
    (r'^bad-weeks$', 'list_bad_xml_files'),

    # single week chart
    (__user_base + r'chart/week/(?P<start>\d*)/$', views.user_week_chart),

    # suggest a listen
    (__user_base + r'who/$', views.who),

    # user chart index
    (__user_base + 'index/$', 'user_data'),

    # top n
    (__user_base + r'top10/' + __date_matcher, views.user_top_n_history),
    (__user_base + r'top10/' + __year_matcher, views.user_top_n_history),
    (__user_base + r'top10/$', views.user_top_n_history, __default_dates),
    (r'^top-n-ajax/$', views.top_n_ajax)

)

def __urlsForPattern(urlpatterns, pattern, view):
    """Creates urls for root, years and arbitrary dates"""
    default_dates  = { 'start': ldates.idx_beginning, 'end': ldates.idx_last_sunday }

    urlpatterns += patterns('twothreefall.lastfmexplorer.views',

        (pattern + '$', view, default_dates),

        # x ago
        (pattern + r'(?P<monthsAgo>\d)month/$', view),
        (pattern + r'(?P<yearsAgo>\d\d?)year/$', view),

        # Arbitrary selection
        (pattern + r'(?P<start>\d+)-(?P<end>\d+)/$', view),

        # Years
        (pattern + r'(?P<year>\d{4})/$', view),
    )

# plain user overview.
__urlsForPattern(urlpatterns, __user_base, 'overview')

# top artist charts
__urlsForPattern(urlpatterns, __user_base + r'chart/', 'user_chart')


# TODO: Django makes it really awkward to include /lastfmexplorer!
class LastfmExplorerSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.25
    def items(self):
        return User.objects.all()
