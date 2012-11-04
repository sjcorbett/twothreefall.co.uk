from django import template

import twothreefall.lastfmexplorer.ldates as ldates

register = template.Library()

@register.filter
def format_week_index(index, format="%Y-%m-%d"):
    date = ldates.date_of_index(index)
    return date.strftime(format)