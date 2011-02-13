import datetime as dt
import logging
import re
import os
from operator import itemgetter

import ldates
from twothreefall.settings import MEDIA_URL, MEDIA_ROOT

from django.db import connection, models
from django.db.models import Sum, Count, Max, Min
from django.core.cache import cache

import matplotlib
import matplotlib.cbook    # placates something or other.
matplotlib.use("Agg")
from matplotlib.pyplot import hist, figure

_BASE_URL  = "http://www.last.fm"
USER_REGEX = r'(?P<username>[a-zA-Z][a-zA-Z0-9_ ]{1,14})'

###############################################################################

class TruncatingCharField(models.CharField):
    def get_prep_value(self, value):
        value = super(TruncatingCharField,self).get_prep_value(value)
        if value:
            return value[:self.max_length]
        return value

class Artist(models.Model):
    name = TruncatingCharField(max_length=75)

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return "%s/music/%s" % (_BASE_URL, self.name)

    class Meta:
        unique_together = ('name',)

class Album(models.Model):
    artist = models.ForeignKey(Artist)
    title  = TruncatingCharField(max_length=100)

    def __unicode__(self):
        return self.title

    def __str__(self):
        return "%s - %s" % (self.artist, self.title)

    def get_absolute_url(self):
        return "%s/music/%s/%s" % (_BASE_URL, self.artist, self.title)

    class Meta:
        unique_together = ('artist', 'title')


class Track(models.Model):
    artist = models.ForeignKey(Artist)
    title  = TruncatingCharField(max_length=100)
    album  = models.ForeignKey(Album, null=True)

    def get_absolute_url(self):
        filler = self.album.title if self.album else "_"
        return "%s/music/%s/%s/%s" % (_BASE_URL, self.artist, filler, self.title)

    def __unicode__(self):
        return self.title

    def __str__(self):
        filler = " (%s)" % (self.album.title,) if self.album else ""
        return "%s - %s%s" % (self.artist, self.title, filler)

    class Meta:
        unique_together = ('artist', 'title', 'album')


###############################################################################

class UserManager(models.Manager):
    def known_user(self, name):
        try:
            self.get(username=name)
            return True
        except:
            return False

    def valid_username(self, name):
        return re.match("^%s$" % (USER_REGEX,), name) is not None

class User(models.Model):
    username   = models.CharField(max_length=15)
    registered = models.DateField()
    last_seen  = models.DateField(auto_now=True)
    last_updated = models.DateField()
    deleted    = models.BooleanField(default=False)

    objects    = models.Manager()
    validity   = UserManager()

    def get_absolute_url(self):
        return "%s/user/%s" % (_BASE_URL, self.username)

    def __unicode__(self):
        return self.username

    def _days_registered(self):
        return (dt.date.today() - self.registered).days
    days_registered = property(_days_registered)

    class Meta:
        ordering = ['username']
        unique_together = ('username',)


class Updates(models.Model):
    user = models.ForeignKey(User)
    num_updates = models.PositiveSmallIntegerField()
    
    def place_in_queue_and_eta(self):
        """
        Returns the number of Updates in the database added before this one
        (i.e. those with a lower primary key) and the total number of requests 
        to Last.fm that'll need to be made before this update is complete.
        """
        # Rubbish to do with lastfmexplorer_user is to placate Django's insistence
        # that raw queries use an ID.
        q = """
            SELECT 
              lastfmexplorer_user.id as id,
              COUNT(lastfmexplorer_updates.id) as piq,
              SUM(lastfmexplorer_updates.num_updates) as total
            FROM 
              lastfmexplorer_updates, lastfmexplorer_user
            WHERE
              lastfmexplorer_updates.id <= %s
            AND
              lastfmexplorer_user.id = 1
            GROUP BY 
              lastfmexplorer_user.id 
        """
        try:
            data = Updates.objects.raw(q, [self.id])[0]
            return data.piq, data.total
        except IndexError:
            return 0, 0

    class Meta:
        unique_together = ('user',)


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


    def chart(self, user, start=None, end=None, count=20):
        qs = self.user_weeks_between(user, start, end) \
                 .values('artist')                     \
                 .annotate(Sum('plays'))               \
                 .order_by('-plays__sum')[:count]
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

    def weekly_play_counts(self, user, start, end, count=None, just_counts=False, \
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
            return (pc if just_counts else (i, pc))
                
        # last_index handles weeks when nothing was played
        if order_by_plays:
            cached.sort(key=itemgetter('plays__sum'), reverse=True)

        if count: cached = cached[:count]

        last_index = start - 1
        for d in cached:
            index = d['week_idx']
            # need to catch up.
            if not order_by_plays and index != (last_index + 1):
                logging.info("catching up from %d to %d" % (last_index+1, index))
                for idx in xrange(last_index+1, index):
                    yield y(idx, 0)
            yield y(index, d['plays__sum'])
            last_index = index


    def save_figure(self, user, figure, fig_name):
        relative = "img/user/%s-%s.png" % (user, fig_name)
        figure.savefig(os.path.join(MEDIA_ROOT, relative), 
                format="png", pad_inches=0, bbox_inches='tight')
        return os.path.join(MEDIA_URL, relative)

    def weekly_play_counts_histogram(self, user, start, end, bins=10):
        wpcs = list(self.weekly_play_counts(user, start, end, just_counts=True))
        fig = figure(figsize=(5,3.5))
        ax  = fig.add_subplot(111)
        ax.grid(True)
        ax.hist(wpcs, bins)
        return self.save_figure(user, fig, 'wpcs-hist-%d-%d' % (start, end))


    def monthly_counts_js(self, user, start, end):
        hist = [0] * 12
        wpcs = self.weekly_play_counts(user, start, end)
        for date, wpc in wpcs:
            bucket = (ldates.date_of_index(date)).month - 1
            hist[bucket] += wpc
        return hist

    def weekly_artist_play_counts_js(self, user, artist, start, end):
        pass

    def weekly_play_counts_js(self, user, start, end):
        wpcs = self.weekly_play_counts(user, start, end)
        n = 0  # number of data points so far

        # Cumulative average:
        # CA_i+1 = CA_i + ((x_i+1 - CA_i) / i+1)
        # where CA_i = last average,
        #      x_i+1 = new entry's value.
        last_avg = 0
        for date_idx, wpc in wpcs:
            n += 1
            average  = last_avg + (( wpc - last_avg) / n )
            last_avg = average
            yield (ldates.js_timestamp_of_index(date_idx), wpc, average)


    def new_artists_in_timeframe(self, user, start, end, count=200):

        # return artist id
        def id(item): return item['artist']

        # every artist listened to between the beginning and the end, NO playcounts
        all_to_end = self.user_weeks_between(user, ldates.idx_beginning, start) \
                         .values('artist')

        # set of ids
        ate = set(map(id, all_to_end))
        del all_to_end

        # every artist listened to between start and end, with playcounts
        start_to_end = self.user_weeks_between(user, start, end) \
                         .values('artist')                       \
                         .annotate(Sum('plays'))                 \
                         .order_by('-plays__sum')

        # find items in start_to_end that aren't in ate.
        max = -1
        for item in start_to_end:
            id = item['artist']
            if id not in ate:
                if max == -1:
                    max = item['plays__sum']
                yield Artist.objects.get(id=id), item['plays__sum'], max
                count -= 1
                if count == 0:
                    break

    def top_n_history(self, user, start, end, count=200): #{{{

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

        artists = set([Artist.objects.get(name="Fleet Foxes").id, \
                       Artist.objects.get(name="Squarepusher").id, \
                   ])

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
    #}}}

    def who_shall_i_listen_to(self, username):
        return Artist.objects.all()

    def weeks_fetched(self, user_id):
        """
        Returns the list of dates that a user has data for.
        """
        return [(x.week_idx, ldates.date_of_index(x.week_idx)) \
                for x in self.raw("SELECT id, week_idx FROM lastfmexplorer_weekdata " + \
                "WHERE user_id=%s GROUP BY week_idx, id", [user_id])]


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



class WeekData(models.Model):
    user   = models.ForeignKey(User)
    week_idx = models.PositiveSmallIntegerField()
    artist = models.ForeignKey(Artist)
    plays  = models.PositiveIntegerField()
    rank   = models.PositiveIntegerField()

    objects = UserWeekDataManager()
    artists = UserArtistWeekDataManager()

    class Meta:
        ordering = ['user', 'week_idx', 'plays', 'artist']
        unique_together = ('user', 'week_idx', 'artist')


###############################################################################

# class TrackPlay(models.Model):
    # user  = models.ForeignKey(User)
    # track = models.ForeignKey(Track)
    # date  = models.DateTimeField()

    # class Meta:
        # ordering = ['date']
        # unique_together = ('user', 'track', 'date')


###############################################################################

class Tag(models.Model):
    tag = TruncatingCharField(max_length=100)
    class Meta:
        unique_together = ('tag',)

class ArtistTags(models.Model):
    artist = models.ForeignKey(Artist)
    tag    = models.ForeignKey(Tag)
    score  = models.PositiveSmallIntegerField()
    class Meta:
        unique_together = ('artist', 'tag')
