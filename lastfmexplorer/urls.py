from django.conf.urls.defaults import *

import views
import ldates
from managers import USER_REGEX

# match usernames
__user_base     = '^user/' + USER_REGEX + '/' 

# match week indexes
__date_matcher  = r'(?P<start>\d+)-(?P<end>\d+)/$'
__year_matcher  = r'(?P<year>\d{4})/$'
__default_dates = { 'start' : ldates.idx_beginning,
                    'end'   : ldates.idx_last_sunday }

urlpatterns = patterns('',
    # start and page
    (r'^$', views.start),

    # updates
    (__user_base + 'update/$', views.update),
    (r'^poll-update$', views.poll_update_status),

    # invalid XML
    (r'^bad-weeks$', views.list_bad_xml_files),

    # plain user overview, first between two dates, second all time.
    (__user_base + __date_matcher, views.overview),
    (__user_base + __year_matcher, views.overview),
    (__user_base + '$', views.overview, __default_dates),

    # single week chart
    (__user_base + r'chart/week/(?P<start>\d*)/$', views.user_week_chart),

    # top artist charts
    (__user_base + r'chart/' + __date_matcher, views.user_chart),
    (__user_base + r'chart/' + __year_matcher, views.user_chart),
    (__user_base + r'chart/$', views.user_chart, __default_dates),

    # suggest a listen
    (__user_base + r'who/$', views.who),

    # user/artist combos
    (__user_base + r'artists/(?P<artists>.*)/$', views.user_and_artist, __default_dates),
    (__user_base + r'artists/(?P<artists>.*)/' + __date_matcher, views.user_and_artist),
    (__user_base + r'artists/(?P<artists>.*)/' + __year_matcher, views.user_and_artist),

)

