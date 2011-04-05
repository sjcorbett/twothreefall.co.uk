from django.http import HttpResponse
from django.http import Http404
from django.shortcuts import render_to_response, redirect, get_object_or_404
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.template import RequestContext
from django.views.decorators.cache import cache_page
from django.views.generic.list_detail import object_list

from datetime import date, timedelta
import logging
import mimetypes
import os
import re
import anyjson

import twothreefall.lastfmexplorer.tasks as tasks
import ldates 
import utils
from models import *
import twothreefall.settings as settings

from celery.result import TaskSetResult 

# TODO: Updates?
def start(request):
    feedback = {}
    given = request.GET.get('username')
    if given:
        given = str(given).strip()
        if User.validity.valid_username(given):
            try:
                u = tasks.get_or_add_user(given)
                target = overview if (not ldates.sensible_to_update(u.last_updated)) else update
                return redirect(target, u)
            except tasks.GetUserFailed as e:
                logging.error(e)
                feedback['errmessage'] = "Either Last.fm is down or you don't exist."
        else:
            feedback['errmessage'] = "Invalid username"

    # TODO: Make this less ugly.
    return render_to_response('index.html', 
                    { 'feedback' : feedback,
                      'given' : given if given else "",
                      'start' : True },
                    context_instance=RequestContext(request))

###############################################################################
# Formalities for every page

def __date_redirection(request, target, start=None, end=None):
    """
    Uses given user/start/end in request.GET to redirect the user to target
    page.  Old start and end are given as placeholders in case they're missing
    in GET.
    """

    GET = request.GET

    try:    
        user = GET['username']
        User.objects.get(username=user)
    except:
        raise Http404
    
    try:
        start = ldates.date_of_string(GET['start'])
    except:
        # TODO: indicate errors, use better default dates (last available for user)
        if not start:
            start = ldates.idx_beginning

    try: 
        end = ldates.date_of_string(GET['end'])
    except: 
        # TODO: indicate errors, use better default dates (last available for user)
        if not end:
            end = ldates.idx_last_sunday

    if start > end:
        temp  = start
        start = end
        end   = temp

    start = ldates.fsoob(start)
    end   = ldates.fsooa(end)

    return redirect(target, user, start, end)


###############################################################################
# Updating user data.
def update(request, username):
    """
    Create a page showing weeks previously retrieved and those still to fetch.
    Queues tasks to be fetched.
    """
    
    user = tasks.get_or_add_user(username)
    template_vars = { 'username' : username } 

    # Check updates table to see if update is already in progress.
    update = None
    try:
        update = Updates.objects.get(user=user)
    except:
        if ldates.sensible_to_update(user.last_updated):
            update = __init_update(user, template_vars)

    if update:
        piq, total = update.place_in_queue_and_eta()
        eta = utils.nicetime(total / 5)
        template_vars.update([('piq', piq - 1), ('num_requests', total), ('eta', eta)])

        return render_to_response('update-nojs.html', template_vars,
                                  context_instance=RequestContext(request))
    else:
        return redirect(overview, user)


def __init_update(user, template_vars):
    # weeks previously fetched
    weeks_done = WeekData.objects.weeks_fetched(user.id)
    weeks_done.reverse()

    # new weeks, or possibly those that failed before.
    # TODO: fail here if couldn't contact last.fm
    chart_list = tasks.chart_list(user.username)
    done_set = set(map(lambda (_,x): x, weeks_done))

    weeks_todo = []
    for start, end in chart_list:
        d = ldates.date_of_timestamp(start)
        if d not in done_set:
            weeks_todo.append((start, end))
    
    if weeks_todo: # != []
        template_vars['skipped'] = False
        weeks_todo.sort(reverse=True)
        user.last_updated = date.today()
        user.save()

        # Create and run taskset.
        t = tasks.user_chart_updates(user.username, weeks_todo)
        template_vars['total_tasks'] = t.total

        # Add to DB
        update = Updates(user=user, num_updates=t.total)
        update.save()

        return update
    else:
        return None

def poll_update_status(request):

    if not 'username' in request.POST:
        raise Http404

    username = request.POST['username']
    user   = get_object_or_404(User, username=username)
    update = get_object_or_404(Updates, user=user)

    # use task id to get status, report back a progress of no. completed.
    pending = cache.get(tasks.user_update_key(username), 0)

    # all complete.  delete from update table.
    if not update or not pending: # == 0
        result['alldone'] = True
        cache.delete(tasks.user_update_key(username))
    else:
        piq, total = update.place_in_queue_and_eta()
        eta = utils.nicetime(total / 5)

        result = { 'pending' : pending,
                   'piq' : piq - 1,
                   'num_requests' : total,
                   'eta' : eta }

    return HttpResponse(anyjson.serialize(result), mimetype="application/json")


###############################################################################
# Interesting bits and pieces.

def staged(target_view, skip_date_shortcuts=False):
    def inner(fn):
        @cache_page(settings.CACHE_USER_TIMEOUT)
        def cleansed(request, username, year=None, start=None, end=None, **kwargs):
            """
            1. Does the user exist?
            2. Are the start and end dates sensible?
            3. Did they submit the date change form?
            """
            try:
                user = User.objects.get(username=username)
            except ObjectDoesNotExist:
                return redirect(update, username)

            # Never updated their data?
            faw = WeekData.objects.first_available_week(user)
            if not isinstance(faw, int):
                raise Http404

            if year:
                year = int(year)
                start, end = ldates.indicies_of_year(year)
            else:
                start = int(start) if (start and int(start) > faw) else faw
                end   = min(int(end) if end else ldates.fsoob(user.last_updated), 
                          ldates.idx_last_sunday)

            # Do this or just fail to 'no data in this range page?'
            if start > end: temp = end; end = start; start = end

            # has the user submitted the change date form?
            if 'username' in request.GET: 
                return __date_redirection(request, cleansed, start, end)

            context = { 'user' : user, 
                        'year' : year,
                        'start' : start,
                        'end' : end,
                        'template' : {
                            # Alter links appropriately
                            'active_view' : cleansed,
                            'kwargs' : kwargs,
                            'skipped_dates' : skip_date_shortcuts,
                            'dstart' : ldates.date_of_index(start),
                            'dend' : ldates.date_of_index(end),
                        }}

            for key, val in kwargs.iteritems():
                context[key] = val
            
            # shortcuts for links to and presentation of dates.
            if not skip_date_shortcuts:
                context['template']['year_shortcuts'] = ldates.years_to_today()
                context['template']['shortcuts'] = ldates.months + ldates.years_ago

            if 'count' in request.GET:
                try:
                    c = int(request.GET['count'])
                    context['count'] = c
                except:
                    pass

            # Fail if there's definitely no data for this range.
            try:
                WeekData.objects.user_weeks_between(user, start, end)[0]
            except IndexError:
                return render_to_response('exploration/no-data-for-dates.html', 
                                          { 'context' : context },
                                          context_instance=RequestContext(request))

            result = fn(request, context)

            return render_to_response(target_view, result,
                    context_instance=RequestContext(request))
        
        cleansed.__name__ = fn.__name__
        cleansed.__dict__ = fn.__dict__
        cleansed.__doc__  = fn.__doc__

        return cleansed
    return inner


@staged('exploration/overview.html')
def overview(request, context):
    """
    Gives a general overview of a user's habits between two dates.
    """
    start = context.get('start')
    end = context.get('end')
    user = context.get('user')

    def new_favourites_string(num=3):
        artists = [(a, c) for a, c, _ in \
                (WeekData.objects.new_artists_in_timeframe(user, start, end, num))]
        def to_s((a, c)):
            return "%s, with %d plays" % (a, c)
        return 'Top %d new artists in this time: %s and %s' % \
                (num, ', '.join(to_s(item) for item in artists[:-1]), \
                 to_s(artists[-1]))

    # vital stats.  TODO: Rework.
    total_plays = WeekData.objects.total_plays_between(user, start, end)
    total_weeks = float(end - start) + 1
    vitals = [
            "%d weeks, %d days" % (total_weeks, total_weeks * 7),
            "%d plays: an average of %.2f songs per week and %.2f per year" \
                    % (total_plays, \
                       total_plays / total_weeks, 
                       total_plays / (total_weeks / 52) if total_weeks >= 52 else total_plays * (52 / total_weeks)),
            # TODO: Reinstate if ever more efficient.
            # new_favourites_string(),
        ]

    # weekly playcounts image and monthly playcounts bar chart
    wpcjs = WeekData.objects.weekly_play_counts_js(user, start, end)
    mcjs  = WeekData.objects.monthly_counts_js(user, start, end)

    # record weeks and overall chart
    rwas  = WeekData.objects.record_weeks(user, start, end)
    rwps  = WeekData.objects.record_week_totals(user, start, end)
    chart = WeekData.objects.chart(user, start, end, count=100)

    # weekly playcounts histogram
    wpc_hist = WeekData.objects.weekly_play_counts_histogram(user, start, end)
    return { 'context' : context,
             'wpc_hist' : wpc_hist,
             'chart' : chart,
             'rwas' : rwas,
             'rwps' : rwps,
             'mcjs' : mcjs,
             'wpcjs' : wpcjs,
             'total_weeks' : total_weeks,
             'vitals' : vitals,
           }

def user_week_chart(request, username, start):
    """ Create a chart for a single week.  """
    return user_chart(request, username, start, start)

@staged('exploration/user-chart.html')
def user_chart(request, context):
    """
    Creates a standard chart.
    """
    start = context.get('start')
    end   = context.get('end')
    count = context.get('count', 100)

    isWeek = start == end
    chart  = WeekData.objects.chart(context.get('user'), start, end, count=count)
    back   = { 'context' : context, 'chart' : chart, 'isWeek' : isWeek }

    if isWeek:
        back['prevW'] = start - 1
        back['nextW'] = start + 1 

    return back


@staged('exploration/new-artists-in-timeframe.html')
def user_new_artists_in_period(request, context):
    """
    Returns artists first listened to in the period between start and end.
    """
    start = context.get('start')
    end   = context.get('end')
    count = context.get('count', 100)

    artists = WeekData.objects.new_artists_in_timeframe(context.get('user'), 
                start, end, count)
    return { 'context' : context, 'artists' : artists }


def user_top_n_history(request, username):
    """
    I haven't decided this yet.
    """
    raise Exception()
    # f, start, end = formalities(request, username, start, end)
    # WeekData.objects.top_n_history(f['user'], start, end)
    # return render_to_response('exploration/top-n-history.html', locals())


@staged('exploration/who.html', skip_date_shortcuts=True)
def who(request, context):
    """
    Recommends an artist user hasn't listened to in a while.
    """
    suggestions = WeekData.objects.who_shall_i_listen_to(context.get('user'))
    return { 'context' : context, 'suggestions' : suggestions }


@staged('exploration/user-and-artist.html', skip_date_shortcuts=True)
def user_and_artist(request, context):
    user = context.get('user')
    start = context.get('start')
    end  = context.get('end')
    artist_names = context.get('artists')
    artists = []

    # look for each artist in the database, ignore if it doesn't exist.
    for artist in artist_names.split("+"):
        try:
            artists.append(Artist.objects.get(name=artist))
        except ObjectDoesNotExist:
            pass

    weekly_plays = WeekData.artists.user_weekly_plays_of_artists(user, artists, start, end)
    return { 'context' : context, 'weekly_plays' : weekly_plays, \
             'array_counter' : xrange(len(weekly_plays)) }


def list_bad_xml_files(request):
    bad_weeks = WeeksWithSyntaxErrors.objects.all()
    return object_list(request, queryset=bad_weeks,
            template_name='weekswithsyntaxerrors_list.html')
