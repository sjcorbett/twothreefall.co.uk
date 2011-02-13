"""
Helpful bitsandpieces.
"""

def nicetime(seconds):
    """
    Returns a string representation of seconds in ..h..m.. format.
    """
    t = ""
    orig = seconds

    # hours
    if seconds >= 3600:
        by3600 = seconds / 3600
        t += "%d hours, " % (by3600,)
        seconds -= 3600 * by3600

    # minutes.  display as ..m, or 00m if no minutes by original value
    # was longer than an hour.
    if seconds >= 60:
        by60 = seconds / 60
        t += "%d minute%s and " % (by60, "s" if by60 > 1 else "")
        seconds -= 60 * by60
    # elif orig >= 3600:
        # t += "00m"

    # and seconds.
    t += "%d seconds" % (seconds % 60,)
    return t


def google_chart_url(self, data, dates):
    """
    Creates a URL for a Google Chart given the data and dates 
    """

    maxd = max(data)

    args = { "cht" : "lc:nda", # chart type.  nda removes axis lines.
             "chs" : "1000x80", #size
             "chd" : "t:" + ",".join(map(str,data)), 
             "chds" : "0,%d" % (maxd,),
             "chxt" : "x", 
             "chxr" : "0,0,%d" % (maxd,),
             # "chxl" : "|".join( dt.date.strftime(d, "%m") for d in dates)
             # "chma" : "0,0,0,0",
           }

    return "http://chart.apis.google.com/chart?%s" % \
            ("&".join("%s=%s" % kv for kv in args.iteritems()),)


