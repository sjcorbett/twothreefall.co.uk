"""
Utilities for handling dates.

Last.fm's charts are effectively release each Sunday noon, and the first charts
were published February 13th 2005.  This information makes storing dates a lot
simpler -- rather than storing a full date we can store an index into the list
where [0] = 13/02/05, [1] = 20/02/05, etc.
"""

from datetime import date, timedelta, datetime

the_beginning = date(2005,2,13)
idx_beginning = 0
ts_beginning  = 1108252800

today         = date.today()

one_week      = timedelta(days=7)
month_in_weeks= 4
year_in_weeks = 52

def date_of_timestamp(ts):
    """Turns a timestamp info a datetime.date."""
    return date.fromtimestamp(ts) 

def index_of_timestamp(ts):
    """Turns a timestamp into a week index."""
    return index_of_sunday(date_of_timestamp(ts))

def date_of_index(idx):
    """Constructs the datetime.date for this week index."""
    if idx < 0:
        raise ValueError("Week index (given %d) cannot be less than zero" % (idx,))
    return the_beginning + (one_week * idx)

def date_of_string(s, fallback=None):
    """Parses a dd/mm/yyyy string into a date."""
    try:
        dt = datetime.strptime(s, '%d/%m/%Y')
        return date(dt.year, dt.month, dt.day)
    except ValueError:
        if fallback: 
            return fallback
        else:
            raise ValueError("date_of_string unable to parse " + s)

def timestamp_of_index(idx):
    """Returns a Unix timestamp for the date represented by idx."""
    seconds_in_week = 604800 # 60 * 60 * 24 * 7
    return ts_beginning + (idx * seconds_in_week)

def js_timestamp_of_index(idx):
    """Javascript represents timestamps in milliseconds."""
    return timestamp_of_index(idx) * 1000

def index_of_sunday(d):
    if d.isoweekday() != 7:
        raise ValueError("date passed to index_of_sunday must be a Sunday")
    return first_sunday_on_or_before(d)

def string_of_date(d):
    return date.strftime(d, "%Y-%m-%d")

def string_of_index(idx):
    return string_of_date(date_of_index(idx))

def __weeks_to(x):
    return (x - the_beginning).days / 7

def first_sunday_on_or_after(d):
    """Returns the index of the first Sunday from the given date inclusive."""
    if d <= the_beginning:
        return 0
    else:
        return __weeks_to(d) + (0 if (d - the_beginning).days % 7 == 0 else 1)

def first_sunday_on_or_before(d):
    """Returns the index of the first Sunday before the given date, inclusive."""
    if d < the_beginning:
        return 0
    return __weeks_to(d)

fsooa = first_sunday_on_or_after
fsoob = first_sunday_on_or_before

idx_last_sunday = first_sunday_on_or_before(today)

def years_to_today():
    return xrange(2005, date.today().year + 1)

def indicies_of_year(year):
    return (fsoob(date(year, 1, 1)), fsooa(date(year, 12, 31)))

def __months_to_indices(num):
    return ("%d months" % (num,) if num > 1 else "month",
            idx_last_sunday - (month_in_weeks * num), idx_last_sunday)
months = map(__months_to_indices, [1, 3, 6])


def __years_to_indices(num):
    return ("%d years" % (num,) if num > 1 else "year",
            max(0, idx_last_sunday - (year_in_weeks * num)), idx_last_sunday)
years_ago = map(__years_to_indices, xrange(1, today.year - the_beginning.year + 1))

def days_between(a, b):
    """Returns the number of days between days a and b."""
    return abs( (a - b).days )

def sensible_to_update(last):
    """Returns True if last update was before today and before 
       the last Sunday, otherwise False."""
    return last < today and last < date_of_index(idx_last_sunday)

