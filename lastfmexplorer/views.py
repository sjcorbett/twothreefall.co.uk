from django.http import HttpResponse
from django.http import Http404
from django.shortcuts import render_to_response, redirect, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.template import RequestContext
from django.views.decorators.cache import cache_page
from django.views.generic.list_detail import object_list

import logging
import anyjson

import twothreefall.settings
import twothreefall.lastfmexplorer.tasks as tasks

from models import *
from chart import Chart
from requester import LastFMRequester

_REQUESTER = LastFMRequester()

def start(request):
    feedback = {}
    given = request.GET.get('username')
    if given:
        given = str(given).strip()
        if User.validity.valid_username(given):
            try:
                u = tasks.get_or_add_user(given, _REQUESTER)
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

def __date_redirection(request, target):
    """
    Uses given user/start/end in request.GET to redirect the user to target page.
    Old start and end are given as placeholders in case they're missing in GET.
    """

    GET = request.GET

    try:    
        user = GET['username']
        User.objects.get(username=user)
    except:
        raise Http404

    start = end = None
    try:
        start = ldates.date_of_string(GET['start'])
    except Exception:
        # TODO: indicate errors, use better default dates (last available for user)
        if not start:
            start = ldates.idx_beginning

    try: 
        end = ldates.date_of_string(GET['end'])
    except Exception:
        # TODO: indicate errors, use better default dates (last available for user)
        if not end:
            end = ldates.idx_last_sunday

    if start > end:
        temp  = start
        start = end
        end   = temp

    start = ldates.fsooa(start)
    end   = ldates.fsooa(end)

    url = reverse(target, args=[user, start, end])

    ignored = ('username', 'start', 'end', 'original_start', 'original_end')
    params = "&".join("%s=%s" % (k,v) if v else k for k,v in GET.iteritems() if k not in ignored)
    if params:
        url += "?" + params

    return redirect(url)


###############################################################################
# Updating user data.
# TODO: Return list of week indexes that are being fetched, render as javascript in template, use to poll for status

def update(request, username):
    """
    Create a page showing weeks previously retrieved and those still to fetch.
    Queues tasks to be fetched.
    """
    
    user = tasks.get_or_add_user(username, _REQUESTER)
    alreadyUpdating = Update.objects.is_updating(user)

    # Skip straight to the overview if there's no reason to be on this page
    if not alreadyUpdating and not ldates.sensible_to_update(user.last_updated):
        return redirect(overview, user)

    # Start a new update
    if not alreadyUpdating:
        alreadyUpdating = tasks.update_user(user, _REQUESTER)

    # Presumably no new data for user
    if not alreadyUpdating:
        return redirect(overview, user)

    # Otherwise, we're updating!
    updating_users = Update.objects.updating_users()
    return render_to_response('update-nojs.html', { 'updating_users': updating_users },
        context_instance=RequestContext(request))


def poll_update_status(request):
    updates = {}
    for user, count in Update.objects.updating_users():
        updates[user.username] = count
    return HttpResponse(anyjson.serialize(updates), mimetype="application/json")


###############################################################################
# Interesting bits and pieces.

# TODO: Does use of ldates.idx_last_sunday only work in the week after the server is started..?

def staged(target_view, skip_date_shortcuts=False):
    def inner(fn):
        @cache_page(twothreefall.settings.CACHE_USER_TIMEOUT)
        def cleansed(request, username, year=None, start=None, end=None, monthsAgo=None, yearsAgo=None, **kwargs):
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
            elif monthsAgo:
                start = max(0, ldates.months_ago(int(monthsAgo)))
                end   = ldates.idx_last_sunday
            elif yearsAgo:
                start = max(0, ldates.years_ago(int(yearsAgo)))
                end   = ldates.idx_last_sunday
            else:
                start = int(start) if (start and int(start) > faw) else faw
                end   = min(int(end) if end else ldates.fsoob(user.last_updated), 
                          ldates.idx_last_sunday)

            # Do this or just fail to 'no data in this range page?'
            if start > end: temp = end; end = start; start = temp

            # has the user submitted the change date form?
            G = request.GET
            if ('original_start' in G) and \
                    (G.get('original_start', start) != start or
                     G.get('original_end', end) != end):
                return __date_redirection(request, cleansed)

            qs = request.META['QUERY_STRING']
            getq = '?' + qs if qs else ''

            context = { 'user' : user, 
                        'request' : request,
                        'year' : year,
                        'start' : start,
                        'end' : end,
                        'template' : {
                            # Alter links appropriately
                            'active_view' : 'lastfmexplorer.views.' + fn.__name__,
                            'kwargs' : kwargs,
                            'skipped_dates' : skip_date_shortcuts,
                            'dstart' : ldates.date_of_index(start),
                            'dend' : ldates.date_of_index(end),
                            'getq' : getq
                        }}

            for key, val in kwargs.iteritems():
                context[key] = val

            # shortcuts for links to and presentation of dates.
            if not skip_date_shortcuts:
                context['template']['year_shortcuts'] = ldates.years_to_today()
                context['template']['years_ago'] = range(1, ldates.today.year - ldates.the_beginning.year + 1)

            if 'count' in G:
                try:
                    c = int(G['count'])
                    context['count'] = c
                except Exception:
                    pass

            # Fail if there's definitely no data for this range.
            if not WeekData.objects.user_weeks_between(user, start, end).exists():
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

    #def new_favourites_string(num=3):
        #artists = [(a, c) for a, c, _ in \
        #        (WeekData.objects.new_artists_in_timeframe(user, start, end, num))]
        #def to_s((a, c)):
        #    return "%s, with %d plays" % (a, c)
        #return 'Top %d new artists in this time: %s and %s' % \
        #        (num, ', '.join(to_s(item) for item in artists[:-1]),
        #         to_s(artists[-1]))

    # vital stats.  TODO: Rework.
    total_plays = WeekData.objects.total_plays_between(user, start, end)
    total_weeks = float(end - start) + 1
    vitals = [
            "<b>%d</b> weeks, <b>%d</b> days" % (total_weeks, total_weeks * 7),
            "<b>%d</b> plays: an average of <b>%.2f</b> songs per week and <b>%.2f</b> per year" \
                    % (total_plays,
                       total_plays / total_weeks, 
                       total_plays / (total_weeks / 52) if total_weeks >= 52 else total_plays * (52 / total_weeks)),
            # TODO: Reinstate if ever more efficient.
            # new_favourites_string(),
        ]

    # weekly playcounts image and monthly playcounts bar chart
    wpcjs = WeekData.objects.weekly_play_counts_js(user, start, end)
    mcjs  = WeekData.objects.monthly_counts_js(user, start, end)

    # record weeks and overall chart
    record_single_artist  = WeekData.objects.record_weeks(user, start, end)
    record_total_plays    = WeekData.objects.record_week_totals(user, start, end)
    record_unique_artists = WeekData.objects.record_unique_artists_in_week(user, start, end)

    chart = Chart(user, start, end)

    # weekly playcounts histogram
    wpc_hist, wpc_hist_step = WeekData.objects.weekly_play_counts_histogram(user, start, end)
    return { 'context' : context,
             'wpc_hist' : wpc_hist,
             'wpc_hist_step' : wpc_hist_step,
             'chart' : chart.chart(),
             'record_single_artist' : record_single_artist,
             'record_total_plays' : record_total_plays,
             'record_unique_artists' : record_unique_artists,
             'mcjs' : mcjs,
             'wpcjs' : wpcjs,
             'total_weeks' : total_weeks,
             'vitals' : vitals,
           }

def user_week_chart(request, username, start):
    """ Create a chart for a single week.  """
    return user_chart(request, username, start=start, end=start)


@staged('exploration/user-chart.html')
def user_chart(request, context):
    """
    Creates a standard chart.
    """
    user  = context.get('user')
    start = context.get('start')
    end   = context.get('end')
    count = context.get('count', 100)

    isWeek = start == end

    G = request.GET
    only_new = 'newmusic' in G
    exclude_months = 'exclude_months' in G

    chart = Chart(user, start, end, count)

    if only_new:
        chart.set_exclude_before_start()

    exclusion = G.get('num_excluded', '')
    max_scrobbles = G.get('max_scrobbles', '')
    if exclude_months:
        if exclusion.isdigit():
            exclusion = int(exclusion) 
            max_scrobbles = int(max_scrobbles) if max_scrobbles.isdigit() else 0
            chart.set_exclude_months(exclusion, max_scrobbles)

    back = { 
        'context': context,
        'chart' : chart.chart(),
        'isWeek' : isWeek,
        'count' : count,
        'only_new': only_new,
        'exclude_months': exclude_months,
        'num_excluded': exclusion,
        'max_scrobbles': max_scrobbles
    }

    if isWeek:
        back['prevW'] = start - 1
        back['nextW'] = start + 1 

    return back


def user_top_n_history(request, username):
    """
    Undecided.
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


def list_bad_xml_files(request):
    bad_weeks = WeeksWithSyntaxErrors.objects.all()
    return object_list(request, queryset=bad_weeks,
            template_name='weekswithsyntaxerrors_list.html')


@staged('exploration/user-data.html', skip_date_shortcuts=True)
def user_data(request, context):
    """
    Report weeks user's scrobbled music in following format:
     (2011, generator of week indexes)
     (2010, ...)
    """
    user  = context.get('user')
    scrobbledin = set(map(lambda x: x['week_idx'],
                          WeekData.objects.filter(user=user.id).values('week_idx').distinct()))
    errors = set(map(lambda w: w.week_idx, WeeksWithSyntaxErrors.objects.filter(user=user.id)))

    years = list(ldates.years_to_today())
    years.reverse()
    years = [ (year, ldates.all_sundays_falling_in(year)) for year in years ]

    return {
        "context" : context,
        "user" : user,
        "years" : years,
        "scrobbledin": scrobbledin,
        "errors": errors
    }


def status(request):
    update_count = Update.objects.count()
    failed_count = Update.objects.filter(status=Update.ERRORED).count()
    pending_count = Update.objects.filter(status=Update.IN_PROGRESS).count()
    complete_count = update_count - failed_count - pending_count
    return render_to_response('status.html', {
            'users': User.objects.count(),
            'artists': Artist.objects.count(),
            'updates': update_count,
            'bad_weeks': WeeksWithSyntaxErrors.objects.count(),
            'bad_week_list': WeeksWithSyntaxErrors.objects.all(),
            'failed_requests': failed_count,
            'successful_requests': complete_count,
            'pending_requests': pending_count
        }, context_instance=RequestContext(request))
