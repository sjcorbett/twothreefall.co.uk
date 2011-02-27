from django.http import HttpResponse
from django import http
from django.shortcuts import render_to_response
from django.conf import settings

import twothreefall.settings

import datetime, re
import mimetypes

basic_context = { 'template' : 
                    { 'MEDIA_URL' : settings.MEDIA_URL,
                      'DEV' : settings.DEV } }

###############################################################################
# Memcached status

def memcached_status(request):

    try:
        import memcache
    except ImportError:
        raise http.Http404

    # if not settings.DEV:
        # raise http.Http404

    # get first memcached URI
    m = re.match(
        "memcached://([.\w]+:\d+)", settings.CACHE_BACKEND
    )

    if not m:
        raise http.Http404

    host = memcache._Host(m.group(1))
    host.connect()
    host.send_cmd("stats")

    class Stats:
        pass

    stats = Stats()

    while 1:
        line = host.readline().split(None, 2)
        if line[0] == "END":
            break
        stat, key, value = line
        try:
            # convert to native type, if possible
            value = int(value)
            if key == "uptime":
                value = datetime.timedelta(seconds=value)
            elif key == "time":
                value = datetime.datetime.fromtimestamp(value)
        except ValueError:
            pass
        setattr(stats, key, value)

    host.close_socket()

    return render_to_response(
        'memcached_status.html', dict(
            stats=stats,
            hit_rate=100 * stats.get_hits / max(stats.cmd_get, 1),
            time=datetime.datetime.now(), # server time
        ))
