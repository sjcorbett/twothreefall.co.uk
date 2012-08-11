"""
A user's chart between two dates.
"""

import ldates
from models import Artist, WeekData

from django.db.models import Sum
from django.core.cache import cache
import settings

class Chart:
    
    def __init__(self, user, start, end, count=100):
        self.user = user
        self.end = end
        self.start = start
        self.count = count
        self.only_new = False
        self.exclude_months = False

    def set_exclude_before_start(self):
        self.only_new = True

    def set_exclude_months(self, months, max_scrobbles=0):
        self.exclude_months = True
        self.months_excluded = months
        self.max_scrobbles_excluded = max_scrobbles

    def chart(self):
        """
        Return generator for chart between dates excluding artists as specified.
        """
        # every artist listened to between start and end, with playcounts
        qs = WeekData.objects.user_weeks_between(self.user, self.start, self.end) \
                 .values('artist')                     \
                 .annotate(Sum('plays'))               \
                 .order_by('-plays__sum')

        excluded = set()
        if self.only_new:
            previous = map(lambda a: a['artist'],
                           WeekData.objects
                            .user_weeks_between(self.user, ldates.idx_beginning, self.start)
                            .values('artist'))
            excluded.update(previous)
            del previous

        if self.exclude_months and self.months_excluded > 0:
            # artists played in last n months:
            n_ago = ldates.idx_last_sunday - (self.months_excluded * 4)
            recent = map(lambda a: a['artist'],
                         WeekData.objects
                          .user_weeks_between(self.user, n_ago, ldates.idx_last_sunday) 
                          .values('artist'))
            excluded.update(recent)
            del recent

        max = None
        to_go = self.count

        # Load artists
        artist_ids = []

        for d in qs:
            # need the maximum for chart widths.
            artist_id = d['artist']
            if artist_id not in excluded:
                artist_ids.append(artist_id)

        # load all artists, transform to id => artist dict
        artists = {}
        for artist in Artist.objects.filter(id__in=artist_ids):
            artists[artist.id] = artist

        for d in qs:
            # need the maximum for chart widths.
            artist_id = d['artist']
            if artist_id not in excluded:
                if not max:
                    max = d['plays__sum']

                yield artists[artist_id], d['plays__sum'], max

                to_go -= 1
                if to_go <= 0:
                    break


