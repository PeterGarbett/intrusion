""" Gets called from intrusion on differing events. Use them to trigger external actions via scripts 
e.g. take additional photos """

import subprocess
import datetime

people = 0
movements = 0
event = datetime.datetime.now()
interval = datetime.timedelta(minutes=30)


def execute(script):
    """Need to start off non-blocking external process"""

    try:
        subprocess.Popen(script)
    except:
        pass


def motion_detected(light):
    """Called when motion has been detected . usually too often in the day"""

    global movements
    global people
    global event

    movements += 1

    #    print("A)people:", people, "movements:", movements)

    #   At night, anything goes
    # 	Make more sensitive after having found a lifeform

    if 0 < people and datetime.datetime.now() - event < interval:
        script = "/home/embed/intrusion/take_photosHT.sh"
        execute(script)
        return True

    return False


def person_detected():
    """Called when lifeform has been detected . usually too late in the day"""
    global people
    global event

    people += 1

    event = datetime.datetime.now()

    #   print("B)people:", people, "movements:", movements)
    script = "/home/embed/intrusion/take_photos.sh"
    execute(script)
    return True


def initialise_trigger():
    """Various things to set up"""
    global people
    global movements
    global event

    people = 0
    movements = 0
    event = datetime.datetime.now()


def low_event_count():
    """Nothing seen for a while, depower to reset the camera - which
    otherwise gets stuck occasionally"""
    script = "/home/embed/intrusion/depower.sh"
    execute(script)


if __name__ == "__main__":
    script = "/home/embed/intrusion/take_photos.sh"
    execute(script)
