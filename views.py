from django import http
from django.shortcuts import render_to_response
from django.conf import settings

import datetime

###############################################################################
# Memcached status

def memcached_status(request):

    try:
        import memcache
    except ImportError:
        raise http.Http404

    host = memcache._Host(settings.CACHE_HOST)
    if host.connect():
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
    else:
        raise http.Http404

