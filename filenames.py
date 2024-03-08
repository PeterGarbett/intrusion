#!/usr/bin/python3
#
#
#

import datetime

# produce time stamp string for use in file naming


def timestampedFilename():
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


def imageName(numberPics, dirname, node, count, timestamp, local):

    debug = True

    if debug:
        print(
            "imagename input: numberpics: ",
            numberPics,
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

    if numberPics:
        outnameStart = dirname + str(count)
    else:
        outnameStart = dirname + timestamp

    outname = outnameStart + "_lb" + str(node) + here + ".jpg"

    return outname


# helper function for reTransmit, since the filename
# determines the action we need to take, and we also may
# need to change it.


import os


def addInLocalToFilename(numberPics, name, returnIdent):

    debug = True

    if debug:
        print("Parse filename:", name)

    filename, file_ext = os.path.splitext(name)

    base, fname = os.path.split(filename)
    base = base + "/"
    nameList = fname
    MandNode = fname.split("_")[-1]

    if debug:
        print("Machine Node", MandNode)

    #   Should be an 'm' followed by at least one digit

    if len(MandNode) < 2:
        return ""

    #   Leading with 'lb'

    if MandNode[0] != "l":
        return ""

    if MandNode[1] != "b":
        return ""

    nodestr = MandNode[2:]

    if debug:
        print("Node:", nodestr)

    try:
        node = int(nodestr)
    except:
        return ""

    if len(nameList) < 3:
        return ""
    else:
        stamp = nameList.replace("_" + MandNode, "")

    #   Stamp is either count or time separted by underscores
    #   depending on numberPics

    if debug:
        print("machine and node:", MandNode)
        print("stamp:", stamp)

    picIdent = stamp.replace(MandNode, "")
    picIdent = picIdent.replace("local", "")
    picIdent = picIdent.rstrip("_")

    if debug:
        print("picture ident:", picIdent)

    # If we remove the underscores we should be left with only digits

    if not picIdent.replace("_", "").isnumeric():
        return ""

    if returnIdent:
        return picIdent

    newname = imageName(numberPics, base, node, picIdent, picIdent, True)

    return newname


import datetime


def txtTimestampToTime(timestamp):

    # Convert someting of the form
    # 2024_03_06_14_24_21_423461
    # to datetime object

    timestamp = timestamp.replace("_", "-", 2)
    timestamp = timestamp.replace("_", " ", 1)
    timestamp = timestamp.replace("_", ":", 2)
    timestamp = timestamp.replace("_", ".", 1)

    # the fact that strptime isn't capable of coping
    # directly with the output of datetime now is
    # really poor.

    try:
        stampNoMs = timestamp[:-7]
        MicrosecondsTXT = timestamp.split(".")[1]
        Microseconds = int(MicrosecondsTXT)
        when = datetime.datetime.strptime(stampNoMs, "%Y-%m-%d %H:%M:%S")
        when = when.replace(microsecond=Microseconds)
    except Exception as e:
        when = 0
        print("Incorrect date format", e)

    return when


def main():

    filename = "/home/peter/2024_03_06_14_24_21_423461_lb42.jpg"
    print("Old name:", filename)
    new = addInLocalToFilename(False, filename, False)
    print("newname:", new)
    filename = "/home/peter/123456789_lb21.jpg"
    print("Old name:", filename)
    new = addInLocalToFilename(True, filename, False)
    print("newname:", new)



if __name__ == "__main__":
    main()
