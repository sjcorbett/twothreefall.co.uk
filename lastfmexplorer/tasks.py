"""
Retrieve data from database and fetch it from last.fm when necessary.
"""
import logging
import lxml.etree as ET
from datetime import date

from celery.task.sets import TaskSet
from celery.task import task

from django.db import transaction
from django.core.cache import cache

from models import *

logging.basicConfig(level=logging.DEBUG)

###############################################################################
########## Helpful XML functions ##############################################

def __iter_over_field(xml, field, et=None):
    """Get an iterator over field in XML."""
    if not et:
        et = ET.fromstring(xml, ET.XMLParser(encoding="utf-8", recover=True))
    return et.getiterator(field)

def __attr(el, a):
    """Get attribute a of element el."""
    return el.attrib[a]

def __elem(el, n):
    """Get text of element n in element el."""
    return el.find(n).text


###############################################################################
########## Exceptions #########################################################

class GetUserFailed(Exception):
    pass

class GetAvailableChartsFailed(Exception):
    pass

class GetWeekFailed(Exception):
    pass

###############################################################################
########## Handling users #####################################################

def get_or_add_user(user, requester):
    """
    Retrieves the User object for the user string arg.  If it doesn't exist 
    then attempt to fetch the information from Last.fm and store it.
    """
    try:
        u = User.objects.get(username=user)
    except User.DoesNotExist:
        req = requester.make("user.getInfo", {'user':user})
        if not req['success']:
            raise GetUserFailed(req['error']['message'])
        et  = ET.fromstring(req['data'])
        if et.get("status") == "ok":
            et  = et.find('user')
            reg = dt.date.fromtimestamp(int(et.find('registered').get('unixtime')))
            # TODO: Use XPath selector (image[@size='medium']) when on Python 2.7
            img = 'http://cdn.last.fm/flatness/catalogue/noimage/2/default_user_medium.png'
            for i in et.findall("image"):
                if i.get('size') == 'medium' and i.text is not None:
                    img = i.text
            u = User.objects.create(username=user, registered=reg, last_updated=reg, image=img)
        else:
            raise GetUserFailed("Are you sure you exist?")
            
    return u


###############################################################################
########## Retrieving available weekly charts #################################

def fetch_chart_list(user, requester):
    """
    Fetches the list of available charts for user.  Returns a generator 
    providing (from, to) timestamp tuples.
    """
    return __available_charts(requester.make('user.getweeklychartlist', {'user':user})['data'])

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

def week_data(user, requester, start, end, kind='artist'):
    """
    Fetches one week's worth of data from Last.fm (using start and end).  kind 
    controls the kind of chart fetched.  Returns a generator over (name, 
    playcount, rank).
    """
    method = "user.getweekly%schart" % (kind,)
    response = requester.make(method, {'user':user, 'from':start, 'to':end})
    if response['success']:
        return response['data']
    else:
        url = requester.url_for_request(method, {'user':user, 'from':start, 'to':end})
        raise GetWeekFailed("Fetch of %s failed: %s" % (url, response['error']['message']))

def _parse_week_artist_data(xml):
    """
    Parses XML of form:
       <artist rank="1">
         <name>Fleet Foxes</name>
         <mbid>..</mbid>
         <playcount>20</playcount>
         <url>http://www.last.fm/music/Fleet+Foxes</url>
       </artist>

    Returns dictionary with key artist id, value (plays, rank)
    """
    data = {}
    for d in __iter_over_field(xml, 'artist'):
        artist = __elem(d, 'name')
        pc     = int(__elem(d, 'playcount'))
        rank   = int(__attr(d, 'rank'))
        a, _ = Artist.objects.get_or_create(name=artist)

        # Truncating this artist's name could cause a key clash
        # Add the playcount to that entry.
        if a.id in data:
            othercount, rank = data[a.id]
            pc += othercount
        data[a.id] = (pc, rank)

    return data

def _parse_week_track_data(xml):
    """
    Parses XML of form:
       <track rank="1">
         <artist>Fleet Foxes</artist>
         <name>Sun It Rises</name>
         <mbid>..</mbid>
         <playcount>20</playcount>
         <url>..</url>
       </track>

    Returns dictionary with key artist id, value (plays, rank)
    """
    data = {}
    for d in __iter_over_field(xml, 'track'):
        artist = __elem(d, 'artist')
        title  = __elem(d, 'name')
        pc     = int(__elem(d, 'playcount'))
        rank   = int(__attr(d, 'rank'))

        a, _ = Artist.objects.get_or_create(name=artist)
        t, _ = Track.objects.get_or_create(title=title, artist=a)

        # Truncating this artist's name could cause a key clash
        # Add the playcount to that entry.
        if t.id in data:
            othercount, rank = data[t.id]
            pc += othercount
        data[t.id] = (pc, rank)

    return data


@transaction.commit_manually
def __save_week_artist_data(user_id, week_idx, wd):
    try:
        for artistid, (plays, rank) in wd.iteritems():
            WeekData.objects.create(user_id=user_id, artist_id=artistid, week_idx=week_idx, plays=plays, rank=rank)
        transaction.commit()
    except Exception, e:
        transaction.rollback()
        logging.error("__save_week_artist_data failed with %s. user: %d, week: %d, message: %s" % (str(type(e)), user_id, week_idx, e.message))
        raise GetWeekFailed(e.message)
        # logging.error(__url_for_request("user.getweeklyartistchart", {'user':user, 'from':start, 'to':end}))

@transaction.commit_manually
def __save_week_track_data(user_id, week_idx, wd):
    try:
        for trackid, (plays, rank) in wd.iteritems():
            WeekTrackData.objects.create(user_id=user_id, track_id=trackid, week_idx=week_idx, plays=plays, rank=rank)
        transaction.commit()
    except Exception, e:
        transaction.rollback()
        logging.error("__save_week_track_data failed with %s. user: %d, week: %d, message: %s" % (str(type(e)), user_id, week_idx, e.message))
        raise GetWeekFailed(e.message)


@task(ignore_result=True)
def fetch_week_data(user, requester, start, end, type):
    """Args: user, instance of Requestor, week start and end timestamps, kind."""

    week_idx = ldates.index_of_timestamp(end)
    u = Update.objects.get(user=user, week_idx=week_idx, status=Update.IN_PROGRESS, type=type)

    if type == Update.ARTIST:
        kind = 'artist'
        parser = _parse_week_artist_data
        saver  = __save_week_artist_data
    elif type == Update.TRACK:
        kind = 'track'
        parser = _parse_week_track_data
        saver  = __save_week_track_data
    else:
        return
        #kind = 'album'
        #parser = __parse_week_track_data
        #saver  = __save_week_track_data

    logging.debug("fetch_week called: %s, %s, %d %d" % (user.username, kind, start, end))

    try:
        xml = week_data(user, requester, start, end, kind)
        wd = parser(xml)
        saver(user.id, week_idx, wd)
        u.status = Update.COMPLETE
    except GetWeekFailed:
        u.status = Update.ERRORED
    except SyntaxError:
        logging.error("request for %s/%d/%d caused a syntax error." % (user, start, end))
        logging.error(xml)
        WeeksWithSyntaxErrors.objects.create(user_id=user.id, week_idx=week_idx)
        u.status = Update.ERRORED
    except Exception, e:
        logging.error("request for %s/%d/%d caused an unknown error: %s" % (user, start, end, e.message))
        logging.error(xml)
        u.status = Update.ERRORED
    finally:
        u.save()

    return u.status


def update_user(user, requester):
    """ Fetch new weeks, or possibly those that failed before."""
    # TODO: fail here if couldn't contact last.fm
    # Have to fetch the chart list from last.fm because their timestamps are awkward, especially
    # those on the first few charts released.
    chart_list = fetch_chart_list(user.username, requester)
    successful_requests = Update.objects.weeks_fetched(user)

    # create taskset and run it.
    update_tasks = []
    updates = []
    with transaction.commit_on_success():
        for start, end in chart_list:
            idx = ldates.index_of_timestamp(end)
            # Skip if this week is before the user signed up
            if not idx < user.first_sunday_with_data:
                # skip if data has already been successfully fetched
                if (idx, Update.ARTIST) not in successful_requests:
                    update = Update(user=user, week_idx=idx, type=Update.ARTIST)
                    updates.append(update)
                    update_tasks.append(fetch_week_data.subtask((user, requester, start, end, Update.ARTIST)))
#                if (idx, Update.TRACK) not in successful_requests:
#                    Update.objects.create(user=user, week_idx=idx, type=Update.TRACK)
#                    update_tasks.append(fetch_week_data.subtask((user, requester, start, end, Update.TRACK)))

    Update.objects.bulk_create(updates)
    ts = TaskSet(update_tasks)
    ts.apply_async()

    user.last_updated = date.today()
    user.save()

    return len(update_tasks) > 0


###############################################################################
########## Retrieving tags for an artist ######################################

@task
def fetch_tags_for_artist(artist_name, requester):
    artist = Artist.objects.get(artist_name)
    aid    = artist.id
    for tag, count in artist_tags(artist_name, requester):
        mtag = Tag.objects.get_or_create(tag=tag)
        at   = ArtistTags.objects.create(artist_id=aid, tag_id=mtag.id)
        yield at

def artist_tags(artist, requester):
    """
    Fetches num tags for artist from Last.fm.  Returns a generator over 
    (tag name, count).
    """
    result = requester.make("artist.getTopTags", {'artist':artist})
    if result['success']:
        return __parse_tags(result['data']) 
    else:
        logging.error("Failed to fetch tags for artist '%s'" % (artist,))
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
