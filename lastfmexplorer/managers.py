"""
Managers for some of the classes in models.py.
"""
import logging

from datetime import datetime, timedelta
from operator import itemgetter

import ldates
import models as m

from django.db import connection, models
from django.db.models import Sum, Count, Min
from django.core.cache import cache


class UpdateManager(models.Manager):
    def is_updating(self, user):
        return self.filter(user=user, status=m.Update.IN_PROGRESS).exists()

    def weeks_fetched(self, user):
        """Returns a set of (week index, update type) tuples"""
        successes = set()
        for success in self.filter(user=user, status=m.Update.COMPLETE):
            successes.add((success.week_idx, success.type))
        return successes

    def updating_users(self):
        """Returns a generator of (user, count of updates in progress)"""
        user_counts = self.values('user').filter(status=m.Update.IN_PROGRESS).annotate(count=Count('user'))
        for entry in user_counts:
            user = m.User.objects.get(id=entry['user'])
            yield user, entry['count']

    def stalled(self):
        """Returns any update that's IN_PROGRESS for more than an hour"""
        oneHourAgo = datetime.today() - timedelta(hours = 1)
        return self.filter(status=m.Update.IN_PROGRESS, requestedAt__lte=oneHourAgo)


# TODO: Drop any filtering done if dates given are the_beginning and today.
class UserWeekDataManager(models.Manager):

    def __single_item(self, query):
        cursor = connection.cursor()
        cursor.execute(query)
        return cursor.fetchone()[0]

    def total_plays(self, user):
        return self.filter(user=user).aggregate(Sum('plays'))['plays__sum']

    def total_plays_between(self, user, start, end):
        return self.user_weeks_between(user, start, end).aggregate(Sum('plays'))['plays__sum']

    def user_weeks_between(self, user, start, end):
        """
        Returns a basic query set of a user's data filtered to be between 
        start and end.
        """
        base = self.filter(user=user.id)
        if start != ldates.idx_beginning or end != ldates.idx_last_sunday:
            if start == end:
                return base.filter(week_idx=start)
            else:
                return base.filter(week_idx__range=(start, end))
        else:
            return base

    def first_available_week(self, user):
        return self.filter(user=user).aggregate(Min('week_idx'))['week_idx__min']

    def record_weeks(self, user, start, end, num=10):
        """
        Returns a generator of artists most played in a single week between
        start and end.
        """
        query = self.user_weeks_between(user, start, end).order_by('-plays')[:num]
        for week in query:
            date = ldates.date_of_index(week.week_idx)
            yield week, date

    def record_week_totals(self, user, start, end, num=10):
        """
        Returns a generator of most songs played in any week between
        start and end.
        """
        for idx, total in \
                self.weekly_play_counts(user, start, end, num, order_by_plays=True):
            yield idx, ldates.date_of_index(idx), total

    def record_unique_artists_in_week(self, user, start, end, num=10):
        """
        Returns a generator of weeks with most unique artists scrobbled.
        """
        qs = self.user_weeks_between(user, start, end) \
                 .values('week_idx') \
                 .annotate(Count('artist')) \
                 .order_by('-artist__count')[:num]
        for r in qs:
            idx = r['week_idx']
            yield idx, ldates.date_of_index(idx), r['artist__count']

    def weekly_play_counts(self, user, start, end, count=None, just_counts=False,
            order_by_plays=False):

        # Use cache, fill cache if data not there.
        cache_key = "%s:%d:%d:weekly_play_counts" % (user.username, start, end)
        cached = cache.get(cache_key)
        if not cached:
            logging.info("Weekly play counts not in cache, fetching from database: " + cache_key)
            qs = self.user_weeks_between(user, start, end) \
                     .values('week_idx')                   \
                     .annotate(Sum('plays'))               \
                     .order_by('week_idx')

            # list() forces evaluation of queryset.
            cached = list(qs)
            cache.set(cache_key, cached)
        else:
            logging.info("Found weekly playcounts in cache with key: " + cache_key)
        def y(i, pc):
            return pc if just_counts else (i, pc)
                
        # last_index handles weeks when nothing was played
        if order_by_plays:
            cached.sort(key=itemgetter('plays__sum'), reverse=True)

        if count: cached = cached[:count]

        last_index = start - 1
        for d in cached:
            index = d['week_idx']
            # need to catch up.
            if not order_by_plays and index != (last_index + 1):
                for idx in xrange(last_index+1, index):
                    yield y(idx, 0)
            yield y(index, d['plays__sum'])
            last_index = index

    def weekly_play_counts_histogram(self, user, start, end, bins=10):
        wpcs = list(self.weekly_play_counts(user, start, end, just_counts=True))
        buckets = [0] * bins
        step = (max(wpcs) / bins) + 1
        for c in wpcs:
            buckets[c / step] += 1
        return buckets, step

    def monthly_counts_js(self, user, start, end):
        hist = [0] * 12
        wpcs = self.weekly_play_counts(user, start, end)
        for date, wpc in wpcs:
            bucket = (ldates.date_of_index(date)).month - 1
            hist[bucket] += wpc
        return hist

    def weekly_play_counts_js(self, user, start, end):
        wpcs = self.weekly_play_counts(user, start, end)
        n = 0  # number of data points so far

        # Cumulative average:
        # CA_i+1 = CA_i + ((x_i+1 - CA_i) / i+1)
        # where CA_i = last average,
        #      x_i+1 = new entry's value.
        last_avg = 0.0
        for date_idx, wpc in wpcs:
            n += 1
            average = last_avg + ((wpc - last_avg) / n)
            last_avg = average
            yield (date_idx, wpc, average)

    def user_weekly_plays_of_artists(self, user_id, artist_id, start, end):
        """
        Returns a basic query set of a user's data filtered to plays of
        particular artists, between start and end.
        """
        query = self.filter(user=user_id, artist=artist_id).order_by('week_idx')
        if start != ldates.idx_beginning or end != ldates.idx_last_sunday:
            query = query.filter(week_idx__range=(start, end))

        return [(week_data.week_idx, week_data.plays) for week_data in query]
