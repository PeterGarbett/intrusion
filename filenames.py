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
    if local:
        here = "local_"
    else:
        here = ""

    if numberPics:
        outname = dirname + here + "m" + str(node) + "_" + str(count) + ".jpg"
    else:
        outname = dirname + here + "m" + str(node) + "_" + timestamp + ".jpg"

    return outname


# helper function for reTransmit, since the filename
# determines the action we need to take, and we also may
# need to change it.


import os


def parseFilename(numberPics, name):

    filename, file_ext = os.path.splitext(name)

    base, fname = os.path.split(filename)
    base = base + "/"
    nameList = fname
    MandNode = fname.split("_")[0]

    #   Should be an 'm' followed by at least one digit

    if len(MandNode) < 2:
        return ""

    #   Leading with an 'm'

    if MandNode[0] != "m":
        return ""

    nodestr = MandNode[1:]

    try:
        node = int(nodestr)
    except:
        return ""

    if len(nameList) < 3:
        return ""
    else:
        stamp = nameList[3:]

    # If we remove the underscores we should be left with only digits

    if not stamp.replace("_", "").isnumeric():
        return ""

    newname = imageName(numberPics, base, node, stamp, stamp, True)

    return newname


def main():

    filename = "/home/peter/m1_2024_03_06_14_24_21_423461.jpg"
    new = parseFilename(False, filename)
    print(new)
    filename = "/home/peter/m1_2.jpg"
    new = parseFilename(True, filename)
    print(new)


if __name__ == "__main__":
    main()
