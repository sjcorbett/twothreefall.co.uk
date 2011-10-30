"""
Managers for some of the classes in models.py.
"""
import re
import logging
from operator import itemgetter

import ldates
import models as m

from django.db import connection, models
from django.db.models import Sum, Count, Min
from django.core.cache import cache

USER_REGEX = r'(?P<username>[a-zA-Z_-][a-zA-Z0-9_ .-]{1,14})'

class UserManager(models.Manager):
    def known_user(self, name):
        try:
            self.get(username=name)
            return True
        except:
            return False

    def valid_username(self, name):
        return re.match("^%s$" % (USER_REGEX,), name) is not None


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
        query = self.user_weeks_between(user, start, end) \
                     .order_by('-plays')[:num]
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
            logging.info("Weekly play counts not in cache: fetching from database")
            qs = self.user_weeks_between(user, start, end) \
                     .values('week_idx')                   \
                     .annotate(Sum('plays'))               \
                     .order_by('week_idx')

            # list() forces evaluation of queryset.
            cached = list(qs)
            cache.set(cache_key, cached)

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
                    logging.info("0 plays on week " + str(ldates.date_of_index(idx)))
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
            average  = last_avg + (( wpc - last_avg) / n )
            last_avg = average
            yield (ldates.js_timestamp_of_index(date_idx), wpc, average)

    def top_n_history(self, user, start, end, count=10):
        """
        Returns in format [
            {'artist': "Radiohead", 'data': [[0,1], [1,2], [2,1]]},
            {'artist': "Fleet Foxes", 'data': [[0,2], [1,1], [2,2]]},
        ]
        """
        import operator
        import heapq
        from collections import defaultdict

        chart     = defaultdict(int)  # artist --> play count
        tracking  = set()
        current_week = 0 #qs[0].week_idx

        # all weekly plays, order by week start then by playcount
        qs = self.user_weeks_between(user, ldates.idx_beginning, end) \
                 .order_by('-plays') \
                 .order_by('week_idx')

        # artist --> [(week index, chart position)]
        artist_positions = defaultdict(list)

        # WeekData object
        for week_data in qs:

            # time has advanced; we've seen another week.  sort this week's movers
            if week_data.week_idx >= start and week_data.week_idx > current_week:

                # update current date
                current_week = week_data.week_idx

                # take top n items from chart, drop playcounts, zip with chart position
                topn  = {}
                index = 1
                for artist, _ in heapq.nlargest(count, chart.iteritems(), operator.itemgetter(1)):
                    artist_positions[artist].append((current_week, index))
                    index += 1

#                set_topn = set(topn)

            # update running chart with new data
            # using week_data.artist here __really__ slows things down!
            # (hello 25000 more queries.)
            id = week_data.artist_id
            chart[id] += week_data.plays

        out = []
        for artist_id, positions in artist_positions.iteritems():
            out.append({
                'artist': m.Artist.objects.get(id=artist_id).name,
                'data': positions
            })
        return out

    def who_shall_i_listen_to(self, username):
        return m.Artist.objects.all()


class UserArtistWeekDataManager(UserWeekDataManager):
    def user_weeks_between(self, user, artists, start, end):
        """
        Returns a basic query set of a user's data filtered to plays of
        particular artists, between start and end.
        """
        base = self.filter(user=user.id).filter(artist__in=artists)
        if start != ldates.idx_beginning or end != ldates.idx_last_sunday:
            return base.filter(week_idx__range=(start, end))
        else:
            return base

    def user_weekly_plays_of_artists(self, user, artists, start, end):

        # initialise the results to a dictionary or artist -> week/playcount,
        # with all playcounts set to zero.  means no need to handle missing 
        # weeks in query set loop.
        prelim_data = [0] * ((end+1) - start) #dict((ldates.js_timestamp_of_index(x), 0) for x in xrange(start, end+1))
        dates = [ ldates.js_timestamp_of_index(idx) for idx in xrange(start, end+1) ]

        results = dict((artist.id, prelim_data[:]) for artist in artists)

        for artist_wd in self.user_weeks_between(user, artists, start, end):
            # place in the appropriate slot in the result list (subtract start)
            results[artist_wd.artist_id][artist_wd.week_idx - start] = artist_wd.plays

        out = {}
        for artist in artists:
            out[artist] = zip(dates, results[artist.id])

        return out

