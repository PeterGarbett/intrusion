" If we want to make night time behaviour differ from daytime, we need to know " 
from suntime import Sun, SunTimeException
import pytz


def daytime(latitude, longitude):
    """Need to know if we have daylight"""

    now = datetime.datetime.utcnow()

# Fiddle to make times comparable

    utc = pytz.UTC
    now = utc.localize(now)

    sun = Sun(latitude, longitude)

    # Get today's sunrise and sunset in UTC

    today_sr = sun.get_sunrise_time()
    today_ss = sun.get_sunset_time()

    return  today_sr < now and now < today_ss
