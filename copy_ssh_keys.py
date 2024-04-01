"""

# We need  a method to establish connections with other boxes without
# fiddling around with the command line.  I can do this I think if I
# copy ssh files from a known location which I define in the config file
# and read from on startup.  I try not to remove exising keys to avoid
# inadvertantly losing comms with the machine.

"""

import os
import shutil


def update_keys(key_file_lock, ssh_keys):
    """look in directory to ee if we have new keys"""

    #   Exceptions here aren't errors so aren't enunciated

    try:
        list_of_files = os.listdir(key_file_lock)
    except:  # File or directory not found... cant' read it
        list_of_files = []

    # No candidates for new keys so finished

    if len(list_of_files) == 0:
        return

    try:
        list_of_files_dest = os.listdir(ssh_keys)
    except:
        #   SSH key directory doesn't exist so finished.
        return

    # Must take great care not to overwrite an ssh key.
    # So we should exclude our list of existing keys
    # from the names we copy
    # We may really really need to overwrite known_hosts and
    # authorized_keys so remove these from the "don't overwrite"
    # list

    try:
        list_of_files_dest.index("authorized_keys")
        list_of_files_dest.remove("authorized_keys")
    except:
        pass  # not there, so dont worry

    try:
        list_of_files_dest.index("known_hosts")
        list_of_files_dest.remove("known_hosts")
    except:
        pass  # not there, so dont worry

    copy_list = [x for x in list_of_files if x not in list_of_files_dest]

    if len(copy_list) == 0:  # 	Nothing to copy so finished
        return

    # Actually do the file copying

    for source in copy_list:
        shutil.copy(key_file_lock + source, ssh_keys + source)
