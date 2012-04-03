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

    # plain user overview, first between two dates, second all time.
    (__user_base + __date_matcher, 'overview'),
    (__user_base + __year_matcher, 'overview'),
    (__user_base + '$', 'overview', __default_dates),

    # single week chart
    (__user_base + r'chart/week/(?P<start>\d*)/$', views.user_week_chart),

    # top artist charts
    (__user_base + r'chart/' + __date_matcher, 'user_chart'),
    (__user_base + r'chart/' + __year_matcher, 'user_chart'),
    (__user_base + r'chart/$', 'user_chart', __default_dates),

    # suggest a listen
    (__user_base + r'who/$', views.who),

    # user/artist combos
    (__user_base + r'artists/(?P<artists>.*)/$', 'user_and_artist', __default_dates),
    (__user_base + r'artists/(?P<artists>.*)/' + __date_matcher, 'user_and_artist'),
    (__user_base + r'artists/(?P<artists>.*)/' + __year_matcher, 'user_and_artist'),

    # user chart index
    (__user_base + 'index/$', 'user_data'),

)

# TODO: Django makes it really awkward to include /lastfmexplorer!
class LastfmExplorerSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.25
    def items(self):
        return User.objects.all()
