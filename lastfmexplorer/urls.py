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

)

def __urlsForPattern(urlpatterns, pattern, view):
    """Creates urls for root, years and arbitrary dates"""
    default_dates  = { 'start': ldates.idx_beginning, 'end': ldates.idx_last_sunday }

    urlpatterns += patterns('twothreefall.lastfmexplorer.views',

        # Named patterns. Seems these override root below, so important these are first
        (pattern + r'month/$',   view, { 'monthsAgo': 1 }),
        (pattern + r'3months/$', view, { 'monthsAgo': 3 }),
        (pattern + r'6months/$', view, { 'monthsAgo': 6 }),
        (pattern + r'year/$',   view, { 'yearsAgo': 1 }),
        (pattern + r'2years/$', view, { 'yearsAgo': 2 }),
        (pattern + r'3years/$', view, { 'yearsAgo': 3 }),
        (pattern + r'4years/$', view, { 'yearsAgo': 4 }),
        (pattern + r'5years/$', view, { 'yearsAgo': 5 }),
        (pattern + r'6years/$', view, { 'yearsAgo': 6 }),
        (pattern + r'7years/$', view, { 'yearsAgo': 7 }),

        # Root
        (pattern + '/$', view, default_dates),

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
