# D:\systemdjango\edu\app\portal\templatetags\portal_extras.py
from django import template

register = template.Library()

DAY_FULL = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
DAY_ABBR = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

@register.filter
def weekday_name(value):
    """1-7 -> Monday..Sunday"""
    try:
        i = int(value)
        if 1 <= i <= 7:
            return DAY_FULL[i-1]
    except Exception:
        pass
    return value

@register.filter
def weekday_abbr(value):
    """1-7 -> Mon..Sun"""
    try:
        i = int(value)
        if 1 <= i <= 7:
            return DAY_ABBR[i-1]
    except Exception:
        pass
    return value
