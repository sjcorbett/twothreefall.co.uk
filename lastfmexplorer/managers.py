"""
Managers for some of the classes in models.py.
"""
import re
import logging

from datetime import datetime, timedelta
from operator import itemgetter

import ldates
import models as m

from django.db import connection, models
from django.db.models import Sum, Count, Min
from django.core.cache import cache

# TODO: Just assume trimmed input is acceptable
USER_REGEX = r'(?P<username>[a-zA-Z0-9_-][a-zA-Z0-9_ -]{1,14})'

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

    def top_n_history(self, user, start, end, count=200):

        from PIL import Image, ImageDraw
        import operator
        import heapq
        from collections import defaultdict

        chart     = defaultdict(int)  # artist --> play count
        last_week = {}                # artist --> (last coordinates tuple)

        weeks_passed = 0

        # all weekly plays, order by week start then by playcount
        qs = self.user_weeks_between(user, ldates.the_beginning, end) \
                 .order_by('-plays') \
                 .order_by('week_idx')

        height = count
        width  = (end - start).days / 7
        h_offset = 12
        w_offset = 4.5

        # (height * width)
        size = (width * w_offset, height * h_offset)
        logging.info(size)

        # final triple initialises background colour
        im = Image.new("RGB", size, (255, 255, 255))
        dr = ImageDraw.Draw(im)

        grey  = (200, 200, 200)
        black = (0, 0, 0)

        current_week = qs[0].week_idx

        import time
        start_week = time.time()

        artists = set([m.Artist.objects.get(name="Fleet Foxes").id,
                       m.Artist.objects.get(name="Squarepusher").id])

        # drawn at least one week
        drawn = False

        # WeekData object
        for week_data in qs:

            # time has advanced; we've seen another week. draw to image.
            if week_data.week_idx >= start and week_data.week_idx > current_week:

                end_week = time.time()

                logging.info(week_data.week_idx)

                # take top n items from chart, drop playcounts, zip with chart position
                topn  = {}
                index = 1
                for artist, _ in heapq.nlargest(count, chart.iteritems(), operator.itemgetter(1)):
                    topn[artist] = index
                    index += 1

                set_topn = set(topn)
                tracking = set(last_week)

                y = weeks_passed * w_offset

                # three sets:
                # 1. artists in top n but not in last_week
                #       -> draw from bottom of image to new position
                for artist in set_topn - tracking:
                    clr = black if artist in artists else grey
                    x   = topn[artist] * h_offset
                    fro = height * h_offset if drawn else x
                    dr.line((y-1, fro, y, x), fill=clr)
                    last_week[artist] = (y, x)

                # 2. artists in top n and in last_week
                #       -> draw from last week to this week
                for artist in set_topn & tracking:
                    clr = black if artist in artists else grey
                    x = topn[artist] * h_offset
                    dr.line(last_week[artist] + (y, x), fill=clr)
                    last_week[artist] = (y, x)

                # 3. artists in last_week but not in top n
                #       -> no longer need to be tracked
                for artist in tracking - set_topn:
                    del last_week[artist]

                # increment weeks passed and update current date
                # last_week = this_week
                weeks_passed += 1
                current_week = week_data.week_idx
                drawn = True

                graphed = time.time()
                logging.info('Collecting week data took %0.3f ms' % ((end_week-start_week)*1000.0))
                logging.info('Imaging took %0.3f ms' % ((graphed-end_week)*1000.0))
                start_week = time.time()

            # update running chart with new data
            # using week_data.artist here __really__ slows things down!
            # (hello 25000 more queries.)
            id = week_data.artist_id
            chart[id] += week_data.plays

        file = "img/%s-topnhist.png" % (user,)
        im.save(file, "PNG")

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

