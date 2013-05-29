import collections

import ldates
from models import Artist, WeekData

from django.db.models import Sum


class Chart(collections.Sequence):
    """
    A user's chart between two dates.
    """

    def __init__(self, user, start, end, count=100):
        self.user = user
        self.end = end
        self.start = start
        self.count = count
        self.only_new = False
        self.exclude_months = False
        self.chart = None
        self.max = None

    def set_exclude_before_start(self):
        self.only_new = True

    def set_exclude_months(self, months, max_scrobbles=0):
        self.exclude_months = True
        self.months_excluded = months
        self.max_scrobbles_excluded = max_scrobbles

    def __getitem__(self, item):
        if not self.chart:
            self._chart()
        return self.chart[item]

    def __len__(self):
        if not self.chart:
            self._chart()
        return len(self.chart)

    def _chart(self):
        """
        Return generator for chart between dates excluding artists as specified.
        """
        # Exclusions
        excluded = set()
        if self.only_new:
            # Note that this will include artists with 0 plays, should they ever end up in WeekData
            previous = map(lambda a: a['artist'],
                           WeekData.objects
                            .user_weeks_between(self.user, ldates.idx_beginning, self.start-1)
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

        # Load artists
        # every artist listened to between start and end, with playcounts
        artist_and_playcount = WeekData.objects.user_weeks_between(self.user, self.start, self.end)\
                 .values('artist')\
                 .annotate(Sum('plays'))\
                 .order_by('-plays__sum')

        artist_ids = []
        to_go = self.count

        # load all artists, transform to id => artist dict
        for d in artist_and_playcount:
            artist_id = d['artist']
            if artist_id not in excluded:
                artist_ids.append(artist_id)
                to_go -= 1
                if to_go <= 0:
                    break
        artists = Artist.objects.in_bulk(artist_ids)

        to_go = self.count
        c = []
        need_max = True
        for d in artist_and_playcount:
            # need the maximum for chart widths.
            artist_id = d['artist']
            if artist_id not in excluded:
                to_go -= 1
                if to_go < 0:
                    break
                if need_max:
                    self.max = d['plays__sum']
                    need_max = False

                c.append((artists[artist_id], d['plays__sum']))

        self.chart = c

    def __repr__(self):
        entries = 'uncalculated' if not self.chart else len(self.chart)
        return "<Chart:%s:%d:%d:%s>" % (self.user, self.start, self.end, entries)