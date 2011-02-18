"""
Retrieve data from database and fetch it from last.fm when necessary.
"""
import StringIO
import datetime as dt
import gzip
import itertools
import logging
import tempfile, os
import urllib2
import xml.etree.cElementTree as ET
from urllib import urlencode
from httplib import BadStatusLine

from celery.task.sets import TaskSet, subtask
from celery.decorators import task

from django.db import connection, transaction
from django.core.cache import cache

import ldates 
from models import Artist, User, WeekData, Updates, Tag, ArtistTags
from twothreefall.settings import LASTFM_SECRET_KEY, LASTFM_API_KEY

logging.basicConfig(level=logging.DEBUG)

###############################################################################

_API_BASE   = 'http://ws.audioscrobbler.com/2.0/'

###############################################################################
########## Helpful XML functions ##############################################

def __iter_over_field(xml, field, et=None):
    """Get an iterator over field in XML."""
    if not et:
        et = ET.fromstring(xml)
    return et.getiterator(field)

def __attr(el, a):
    """Get attribute a of element el."""
    return el.attrib[a]

def __elem(el, n):
    """Get text of element n in element el."""
    return el.find(n).text


###############################################################################
########## Retrieving available weekly charts #################################

def chart_list(user):
    """
    Fetches the list of available charts for user.  Returns a generator 
    providing (from, to) timestamp tuples.
    """
    return __available_charts( \
             __request('user.getweeklychartlist', {'user':user})['data'])

def __available_charts(xml):
    """
     Parses XML of form:
        <chart from="1108296002" to="1108900802"/>
        <chart from="1108900801" to="1109505601"/>

     Returns generator providing (from, to) tuples.
    """
    weeks = __iter_over_field(xml, 'chart')

    for w in weeks:
        yield (int(__attr(w, 'from')), int(__attr(w, 'to')))


###############################################################################
########## Retrieving one week's data #########################################

def week_data(user, start, end, kind='artist'):
    """
    Fetches one week's worth of data from Last.fm (using start and end).  kind 
    controls the kind of chart fetched.  Returns a generator over (name, 
    playcount, rank).
    """
    method = "user.getweekly%schart" % (kind,)
    return __parse_week_data( \
             __request(method, {'user':user, 'from':start, 'to':end})['data'])

def __parse_week_data(xml):
    """
    Parses XML of form:
       <artist rank="1">
         <name>Fleet Foxes</name>
         <mbid>..</mbid>
         <playcount>20</playcount>
         <url>http://www.last.fm/music/Fleet+Foxes</url>
       </artist>

    Returns generator over (name, playcount, rank).
    """
    for d in __iter_over_field(xml, 'artist'):
        yield (__elem(d, 'name'),
         int(__elem(d, 'playcount')),
         int(__attr(d, 'rank')))


###############################################################################
########## Handling users #####################################################

class GetUserFailed(Exception):
    pass

def get_or_add_user(user):
    """
    Retrieves the User object for the user string arg.  If it doesn't exist 
    then attempt to fetch the information from Last.fm and store it.
    """
    try:
        u = User.objects.get(username=user)
    except User.DoesNotExist:
        req = __request("user.getInfo", {'user':user})
        if not req['success']:
            raise GetUserFailed(req['error']['message'])
        et  = ET.fromstring(req['data'])
        if et.get("status") == "ok":
            et  = et.find('user')
            reg = dt.date.fromtimestamp(int(et.find('registered').get('unixtime')))
            u   = User.objects.create(username=user, registered=reg, last_updated=reg)
        else:
            raise GetUserFailed("Are you sure you exist?")
            
    return u

def user_update_key(username):
    return "update" + username

def user_chart_updates(username, weeks):
    logging.info("user_chart_updates")
    user = get_or_add_user(username)

    # set cache to number of tasks to complete with a long timeout to make
    # sure it doesn't get lost between polls.  Will be deleted when unnecessary.
    cache.set(user_update_key(username), len(weeks), timeout=7200)

    # create taskset and run it.
    tasks = [ fetch_week.subtask((user, start, end)) for start, end in weeks ]
    tasks.append(finish_update.subtask((user,)))
    ts = TaskSet(tasks)
    return ts.apply_async()


@task(ignore_result=True)
def fetch_week(user, start, end):

    logging.info("fetch_week called: %s, %d %d" % (user.username, start, end))

    # WARNING: Potential for races if decr isn't atomic.  Memcached is.
    cache.decr(user_update_key(str(user.username)))

    week_idx = ldates.index_of_timestamp(start)
    result = {'success' : True, 'week_idx' : week_idx}
    
    incomplete = True
    max_retries = 2
    attempt = 0
    data = None
    while incomplete and attempt < max_retries:
        try:
            data = week_data(user.username, start, end)
            incomplete = False
        except BadStatusLine:
            logging.warn("fetch_week caught BadStatusLine, attempt %d" % (attempt,))
            attempt += 1
        except KeyError:
            logging.warn("fetch_week caught KeyError, attempt %d" % (attempt,))
            attempt += 1
        except SyntaxError:
            logging.error("request for %s/%d/%d caused a syntax error" % (user, start, end))
            incomplete = False

    if data:
        for artist, plays, rank in data:
            a, _ = Artist.objects.get_or_create(name=artist)
            try:
                WeekData.objects.create(user_id=user.id, artist_id=a.id, \
                        week_idx=week_idx, plays=plays, rank=rank)
            except IntegrityError:
                logging.error("IntegrityError creating weekdata object: " + \
                        "user: %d, artist: %d, week_idx: %d\nuser/start/end: %s/%d/%d" % (user.id, a.id, week_idx, user, start, end)) 
    else:
        result['success'] = False

    return result


@task(ignore_result=True)
def finish_update(user):
    update = Updates.objects.get(user=user)
    update.delete()
    return True


###############################################################################
########## Retrieving tags for an artist ######################################

@task
def fetch_tags_for_artist(artist_name):
    artist = Artist.objects.get(artist_name)
    aid    = artist.id
    for tag, count in artist_tags(artist_name):
        mtag = Tag.objects.get_or_create(tag=tag)
        at   = ArtistTags.objects.create(artist_id=aid, tag_id=mtag.id)

def artist_tags(artist):
    """
    Fetches num tags for artist from Last.fm.  Returns a generator over 
    (tag name, count).
    """
    result = __request("artist.getTopTags", {'artist':artist})
    if result['success']:
        return __parse_tags(result['data']) 
    else:
        logging.error("Failed to fetch tags for artist '%s'" % (artist))
        return [] 

def __parse_tags(xml):
    """
    Parses XML of form:
    <toptags artist="Cher">
      <tag>
        <name>pop</name>
        <url>http://www.last.fm/tag/pop</url>
      </tag>
      ...
    </toptags>
    Returns generator over (tag name, count).
    """
    for t in __iter_over_field(xml, 'tag'):
        count = int(__elem(t, 'count'))
        if count > 0:
            yield(__elem(t, 'name'), count)
        else:
            return


###############################################################################
########## HTTP requests ######################################################
# TODO: Better error handling
# TODO: Handle HTTP 503s.
def __request(method, extras=None):
    """
    Requests data from Last.fm.  
      method: string name of an API method
      extras: any arguments, whether required or optional.
    """

    args = urlencode(extras) if extras else ""
    query = "%s?method=%s&api_key=%s&%s" % (_API_BASE, method, LASTFM_API_KEY, args)

    logging.info(query)
    req = urllib2.Request(query)
    req.add_header('Accept-encoding', 'gzip')
    req.add_header('User-agent', 'Last.fm Explorer')

    result = { 'success' : True }

    try:
        r = urllib2.urlopen(req, timeout=60).read()
        result['data'] = __unzip(r)

    except urllib2.HTTPError, e:
        logging.error("Error accessing " + query + " - " + str(e.code))
        result['success'] = False
        result['error'] = { 'code' : e.code, 'message' : e.msg }
        
    except urllib2.URLError, e:
        logging.error("Failed to fetch " + query + ' - URLError.')
        result['success'] = False
        result['error'] = { 'message' : e.reason }

    return result

def __unzip(data):
    """
    Unzips a gzipped stream.  Since gzip reads a file the data is represented as
    a file in memory.
    """
    compressed = StringIO.StringIO(data)
    gzipper    = gzip.GzipFile(fileobj=compressed)
    return gzipper.read()



## def recent_tracks(user):
##     page = 1
##     totalPages = 2
##     rts = []
##     while page <= totalPages:
##         xml = __request("user.getRecentTracks",
##                 {'user':user.username, 'page':page, 'limit':50})
##         et = ET.fromstring(xml)
##         print xml
##         totalPages = int(__attr(et.find('recenttracks'), ('totalPages')))
##         for artist, track, album, datetime in __parse_recent_tracks(et):
##             print artist, track, album, datetime
##             _artist, _ = Artist.objects.get_or_create(name=artist)
##             if album:
##                 _album,  _ = Album.objects.get_or_create( \
##                                  artist=_artist, title=album)
##             else:
##                 _album = None
##             _track,  _ = Track.objects.get_or_create( \
##                              artist=_artist, title=track, album=_album)
##             rts.append(TrackPlay(user=user, track=_track, date=datetime))
##         page += 1000000
##     return rts
##
## def __parse_recent_tracks(element_tree):
##     """
##     Parses XML of form:
##     <track>
##         <artist mbid="28503ab7-...">Dream Theater</artist>
##         <name>Pull Me Under</name>
##         <album mbid="f20971f2-...">Images and Words</album>
##         <date uts="1265484385">6 Feb 2010, 19:26</date>
##         ...
##     </track>
##     <track>
##     """
##     e = __elem
##     for track in element_tree.getiterator('track'):
##         if not track.get('nowplaying'): # doesn't have a date
##             yield \
##                (e(track, 'artist'),
##                 e(track, 'name'),
##                 e(track, 'album'),
##                 dt.datetime.fromtimestamp( \
##                      float(track.find('date').get('uts'))))
##
