""" produce time stamp string for use in file naming """

import os
import datetime


def time_stamped_filename():
    """Generate string suitable for part of a filename from the current time"""
    presentday = datetime.datetime.now()

    name = str(presentday)

    #   Keep a delimiter but make it compatible with being a filename

    name = name.replace(".", "_")
    name = name.replace("-", "_")
    name = name.replace(" ", "_")
    name = name.replace(":", "_")
    filename = name

    return filename


# Numbering the pictures is useful for debugging
# but overwrites on every restart


def image_name(number_pics, dirname, node, count, timestamp, local):
    """Form image name using timestamp or a count"""
    debug = False

    if debug:
        print(
            "imagename input: numberpics: ",
            number_pics,
            "dir:",
            dirname,
            "node:",
            node,
            "<count:",
            count,
            "timestamp:",
            timestamp,
            "\n`local:",
            local,
        )

    if local:
        here = "_local"
    else:
        here = ""

    if number_pics:
        outname_start = dirname + str(count)
    else:
        outname_start = dirname + timestamp

    outname = outname_start + "_lb" + str(node) + here + ".jpg"

    return outname


# helper function for reTransmit, since the filename
# determines the action we need to take, and we also may
# need to change it.


def add_in_local_to_filename(number_pics, name, return_ident):
    """Modify the filename by adding in local to signify its been sent offsite"""
    debug = False

    if debug:
        print("Parse filename:", name)

    filename, file_ext = os.path.splitext(name)

    base, fname = os.path.split(filename)
    base = base + "/"
    name_list = fname
    m_and_node = fname.split("_")[-1]

    if debug:
        print("Machine Node", m_and_node)

    #   Should be an 'm' followed by at least one digit

    if len(m_and_node) < 2:
        return ""

    #   Leading with 'lb'

    if m_and_node[0] != "l":
        return ""

    if m_and_node[1] != "b":
        return ""

    nodestr = m_and_node[2:]

    if debug:
        print("Node:", nodestr)

    try:
        node = int(nodestr)
    except:
        return ""

    if len(name_list) < 3:
        return ""

    stamp = name_list.replace("_" + m_and_node, "")

    #   Stamp is either count or time separted by underscores
    #   depending on number_pics

    if debug:
        print("machine and node:", m_and_node)
        print("stamp:", stamp)

    pic_ident = stamp.replace(m_and_node, "")
    pic_ident = pic_ident.replace("local", "")
    pic_ident = pic_ident.rstrip("_")

    if debug:
        print("picture ident:", pic_ident)

    # If we remove the underscores we should be left with only digits

    if not pic_ident.replace("_", "").isnumeric():
        return ""

    if return_ident:
        return pic_ident

    newname = image_name(number_pics, base, node, pic_ident, pic_ident, True)

    return newname


def txt_timestamp_to_time(timestamp):
    """

    Convert someting of the form
     2024_03_06_14_24_21_423461
     to datetime object

    """

    timestamp = timestamp.replace("_", "-", 2)
    timestamp = timestamp.replace("_", " ", 1)
    timestamp = timestamp.replace("_", ":", 2)
    timestamp = timestamp.replace("_", ".", 1)

    # the fact that strptime isn't capable of coping
    # directly with the output of datetime now is
    # really poor.

    try:
        stamp_noms = timestamp[:-7]
        microseconds_text = timestamp.split(".")[1]
        microseconds = int(microseconds_text)
        when = datetime.datetime.strptime(stamp_noms, "%Y-%m-%d %H:%M:%S")
        when = when.replace(microsecond=microseconds)
    except Exception as err:
        when = 0
        print("Incorrect date format", err)

    return when
