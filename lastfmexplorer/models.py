import datetime as dt

import ldates
import managers

from django.db import models

_LASTFM  = "http://www.last.fm"
_LASTFM_EXAMPLE_API_KEY = "b25b959554ed76058ac220b7b2e0a026"

###############################################################################

MAX_ARTIST_NAME_LENGTH = 75

class TruncatingCharField(models.CharField):
    def get_prep_value(self, value):
        value = super(TruncatingCharField,self).get_prep_value(value)
        if value:
            return value[:self.max_length]
        return value


class Artist(models.Model):
    name = TruncatingCharField(max_length=MAX_ARTIST_NAME_LENGTH)
    # e.g. 80e577ba-841f-43ba-9f32-72e7c1692336
    mbid = models.CharField(max_length=36, null=True)

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return "%s/music/%s" % (_LASTFM, self.name)

    class Meta:
        unique_together = ('name', 'mbid')


class Album(models.Model):
    artist = models.ForeignKey(Artist)
    title  = TruncatingCharField(max_length=100)

    def __unicode__(self):
        return self.title

    def __str__(self):
        return "%s - %s" % (self.artist, self.title)

    def get_absolute_url(self):
        return "%s/music/%s/%s" % (_LASTFM, self.artist, self.title)

    class Meta:
        unique_together = ('artist', 'title')


class Track(models.Model):
    artist = models.ForeignKey(Artist)
    title  = TruncatingCharField(max_length=100)

    def get_absolute_url(self):
        return "%s/music/%s/_/%s" % (_LASTFM, self.artist, self.title)

    def __unicode__(self):
        return self.title

    def __str__(self):
        return "%s - %s" % (self.artist, self.title)

    class Meta:
        unique_together = ('artist', 'title')


###############################################################################

class User(models.Model):
    username   = models.CharField(max_length=15)
    registered = models.DateField()
    last_seen  = models.DateField(auto_now=True)
    last_updated = models.DateField()
    deleted    = models.BooleanField(default=False)
    image      = models.URLField()

    objects    = models.Manager()
    validity   = managers.UserManager()

    def get_absolute_url(self):
        return "%s/user/%s" % (_LASTFM, self.username)

    def __unicode__(self):
        return self.username

    def _days_registered(self):
        return (dt.date.today() - self.registered).days
    days_registered = property(_days_registered)

    class Meta:
        ordering = ['username']
        unique_together = ('username',)


class Update(models.Model):
    IN_PROGRESS = 0
    COMPLETE = 1
    ERRORED = 2
    STATUSES = (
        (IN_PROGRESS, "In progress"),
        (COMPLETE, "Complete"),
        (ERRORED, "Errored")
    )
    user = models.ForeignKey(User)
    week_idx = models.PositiveSmallIntegerField()
    status = models.IntegerField(default=IN_PROGRESS, choices=STATUSES)

    objects = managers.UpdateManager()

    def __unicode__(self):
        return "%s:%d:%s" % (self.user, self.week_idx, self.STATUSES[self.status][1])

class WeekData(models.Model):
    """
    Weekly artist plays per user
    """
    user   = models.ForeignKey(User)
    week_idx = models.PositiveSmallIntegerField(db_index=True)
    artist = models.ForeignKey(Artist)
    plays  = models.PositiveIntegerField()
    rank   = models.PositiveIntegerField()

    objects = managers.UserWeekDataManager()
    artists = managers.UserArtistWeekDataManager()

    def __unicode__(self):
        return "<WeekData: %s/%d/%s/%d>" % \
                (self.user.username, self.week_idx, self.artist.name, self.plays)

    class Meta:
        unique_together = ('user', 'week_idx', 'artist')


class WeekTrackData(models.Model):
    """
    Weekly track plays per user
    """
    user   = models.ForeignKey(User)
    week_idx = models.PositiveSmallIntegerField(db_index=True)
    track  = models.ForeignKey(Track)
    plays  = models.PositiveIntegerField()
    rank   = models.PositiveIntegerField()

    objects = managers.UserWeekDataManager()

    def __unicode__(self):
        return "<WeekTrackData: %s/%d/%s/%d>" %\
               (self.user.username, self.week_idx, self.track, self.plays)

    class Meta:
        unique_together = ('user', 'week_idx', 'track')


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


###############################################################################

class WeeksWithSyntaxErrors(models.Model):
    user = models.ForeignKey(User)
    week_idx = models.PositiveSmallIntegerField(db_index=True)

    def __unicode__(self):
        start = ldates.string_of_index(self.week_idx)
        end   = ldates.string_of_index(self.week_idx + 1)
        return "%s to %s" % (start, end)

    def get_absolute_url(self):
        sts = ldates.timestamp_of_index(self.week_idx)
        ets = ldates.timestamp_of_index(self.week_idx + 1)
        return "http://ws.audioscrobbler.com/2.0/?method=user.getweeklyartistchart&user=%s&api_key=%s&from=%d&to=%d" % \
                (self.user.username, _LASTFM_EXAMPLE_API_KEY, sts, ets)
