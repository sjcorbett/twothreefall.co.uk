"""
Retrieve data from database and fetch it from last.fm when necessary.
"""
import logging
import xml.etree.cElementTree as ET
from datetime import date

from celery.task.sets import TaskSet
from celery.task import task

from django.db import transaction

from models import *

logging.basicConfig(level=logging.DEBUG)

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
        return __parse_week_data(response['data']) 
    else:
        raise GetWeekFailed(response['error']['message'])

def __parse_week_data(xml):
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
        mbid   = __elem(d, 'mbid')

        mbid   = mbid.strip() if mbid else ""
        a, _ = Artist.objects.get_or_create(name=artist, mbid=mbid)

        # Truncating this artist's name could cause a key clash
        # Add the playcount to that entry.
        if a.id in data:
            othercount, rank = data[a.id]
            pc += othercount
        data[a.id] = (pc, rank)

    return data


@transaction.commit_manually
def __save_week_data(user_id, week_idx, wd):
    try:
        for artistid, (plays, rank) in wd.iteritems():
            WeekData.objects.create(user_id=user_id, artist_id=artistid,
                    week_idx=week_idx, plays=plays, rank=rank)
        transaction.commit()
    except Exception, e:
        transaction.rollback()
        logging.error("__save_week_data failed with %s. user: %d, week: %d, message: %s" % (str(type(e)), user_id, week_idx, e.message))
        raise GetWeekFailed(e.message)
        # logging.error(__url_for_request("user.getweeklyartistchart", {'user':user, 'from':start, 'to':end}))


@task(ignore_result=True)
def fetch_week(user, requester, start, end):
    """Args: user, instance of Requestor, week start and end timestamps."""

    logging.debug("fetch_week called: %s, %d %d" % (user.username, start, end))

    week_idx = ldates.index_of_timestamp(end)
    u = Update.objects.get(user=user, week_idx=week_idx, status=Update.IN_PROGRESS)

    try:
        wd = week_data(user, requester, start, end)
        __save_week_data(user.id, week_idx, wd)
        u.status = Update.COMPLETE
    except GetWeekFailed:
        u.status = Update.ERRORED
    except SyntaxError:
        logging.error("request for %s/%d/%d caused a syntax error" % (user, start, end))
        WeeksWithSyntaxErrors.objects.create(user_id=user.id, week_idx=week_idx)
        u.status = Update.ERRORED
    finally:
        u.save()

    return u.status

def update_user(user, requester):
    """ Fetch new weeks, or possibly those that failed before."""
    # TODO: fail here if couldn't contact last.fm
    chart_list = fetch_chart_list(user.username, requester)
    done_set = set(Update.objects.weeks_fetched(user))

    # create taskset and run it.
    update_tasks = []
    for start, end in chart_list:
        idx = ldates.index_of_timestamp(end)
        if idx not in done_set:
            Update.objects.create(user=user, week_idx=idx)
            update_tasks.append(fetch_week.subtask((user, requester, start, end)))

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
