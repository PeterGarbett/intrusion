'''

Manage low storage conditions

'''



import os
import shutil

SUPPRESSDELETION = False


def running_low(folder, limit):
    """

    See if we are running out of local storage
    and delete a few oldest files if so
    This is to avoid a problem on unattended infrequently managed systems

    """


    try:
        total, used, free = shutil.disk_usage(folder)
    except:
        return False

    return bool(free < limit)


def delete_oldest(folder):
    """

    Make some space by deleting the oldest file
    folder is the name of the folder in which we
    have to perform the delete operation
    changing the current working directory
    to the folder specified
    Protect from exception in case this doesn't exist
    to protect us from inappropriate file removal

    """

    debug = False

    try:
        os.chdir(os.path.join(os.getcwd(), folder))
    except Exception as err:
        print(err)
        return

    list_of_files = os.listdir(".")
    if len(list_of_files) == 0:
        return

    oldest_file = min(list_of_files, key=os.path.getctime)

    if debug:
        print("Oldest data file", folder + oldest_file, " to be deleted")

    if not SUPPRESSDELETION:
        try:
            os.remove(os.path.abspath(folder + oldest_file))
        except Exception as err:
            print(err)
            return


def make_space(folder, limit):
    ''' If space is low,  delete a few, releasing lock in between '''
    space_low = running_low(folder, limit)
    if space_low:  # delete a few, releasing lock in between
        delete_oldest(folder)
        delete_oldest(folder)
        delete_oldest(folder)
