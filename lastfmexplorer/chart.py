"""
A user's chart between two dates.
"""

from models import Artist, WeekData

from django.db.models import Sum
from django.db.models import Q
from django.core.cache import cache

class Chart:
    
    def __init__(self, user, start, end, count=100):
        self.user = user
        self.end = end
        self.start = start
        self.count = count

    def set_exclude_before_start(self):
        self.only_new = True

    def set_exclude_months(self, months, max_scrobbles=0):
        self.exclude_months = True
        self.months_excluded = months
        self.max_scrobbles_excluded = max_scrobbles

    def chart(self):
    
        qs = WeekData.objects.user_weeks_between(self.user, self.start, self.end) \
                 .values('artist')                     \
                 .annotate(Sum('plays'))               \
                 .order_by('-plays__sum')[:self.count]

        max = None
        for d in qs:
            # need the maximum for chart widths.
            if not max:
                max = d['plays__sum']

            artist = cache.get("artist%d" % (d['artist'],))
            if not artist:
                artist = Artist.objects.get(id=d['artist'])
                cache.set("artist%d" % (d['artist'],), artist, 10000)

            yield artist, d['plays__sum'], max


