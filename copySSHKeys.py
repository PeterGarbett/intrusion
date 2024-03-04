#!/usr/bin/python3

# We need  a method to establish connections with other boxes without
# fiddling around with the command line.  I can do this I think if I
# copy ssh files from a known location which I define in the config file
# and read from on startup.  I try not to remove exising keys to avoid
# inadvertantly losing comms with the machine.

import os
import shutil

def update_keys(keyFileLoc, sshKeys):

    #   look in directory holding new keys

    try:
        list_of_files = os.listdir(keyFileLoc)
    except Exception as e:
        list_of_files = []

    # No candidates for new keys so finished

    if len(list_of_files) == 0:
        return

    try:
        list_of_filesDest = os.listdir(sshKeys)
    except Exception as e:
        #   SSH key directory doesn't exist so finished.
        return

    # Must take great care not to overwrite an ssh key.
    # So we should exclude our list of existing keys
    # from the names we copy
    # We may really really need to overwrite known_hosts and
    # authorized_keys so remove these from the "don't overwrite"
    # list

    try:
        auPos = list_of_filesDest.index("authorized_keys")
        list_of_filesDest.remove("authorized_keys")
    except:
        pass  # not there, so dont worry

    try:
        knownHPos = list_of_filesDest.index("known_hosts")
        list_of_filesDest.remove("known_hosts")
    except:
        pass  # not there, so dont worry

    copyList = [x for x in list_of_files if x not in list_of_filesDest]

    if len(copyList) == 0:	#	Nothing to copy so finished
        return
    else:
        for source in copyList:
            shutil.copy(keyFileLoc + source, sshKeys + source)
