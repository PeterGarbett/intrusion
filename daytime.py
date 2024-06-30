from datetime import datetime
from suntime import Sun, SunTimeException
import pytz


def daytime(location):

    latitude = location[0]
    longitude =  location[1]

    now = datetime.utcnow()
    utc = pytz.UTC
    now = utc.localize(now)

    sun = Sun(latitude, longitude)

    # Get today's sunrise and sunset in UTC

    today_sr = sun.get_sunrise_time()
    today_ss = sun.get_sunset_time()

    if today_sr < now and now < today_ss:
        return True
    else:
        return False



