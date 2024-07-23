""" Separated out file transfer utility """
import sys
import glob
import os
import multiprocessing
from time import sleep
import filenames
import transfer


retransmissionActive = multiprocessing.Value("i", 0)
window3 = 67
jpeg_store = "/exdrive/Snapshots/Local/"
hostname = "garbett.cloudns.org"
remote_path = "/exdrive/Snapshots/Local/"
user = "embed"


number_pictures = False


def re_transmit(lock, user, hostname, final_dest, remote_path):
    """
    re_transmit - which is in fact a misnomer it's more like retry
    transferring something that didn't go the first time.
    This is intended to be a background task and would come into play
    if the connection to the remote machine went down transiently
    I assumme here we aren't sending data out to a machine on the LAN
    the main case of interest is lost internet, so we test for it
    working 1st
    """

    debug = True

    while True:
        retransmissionActive.value += 1  # Watchdog
        #        sleep(window3)  # Whose update rate is low: beware
        retransmissionActive.value += 1  # Watchdog

        try:
            test_hostname = "google.com"  # example
            response = os.system("ping -c 1 -w2 " + test_hostname + " > /dev/null 2>&1")
        except Exception as err:
            print(err)
            sleep(10)
            continue

        if response != 0:
            if debug:
                print("File transmission not possible, no internet connection")
            sleep(10)
            continue

        acq = lock.acquire(block=False)
        if not acq:
            continue

        # get candidate image files (excluding live)
        # This only works well with timestamped files

        imgnames = sorted(glob.glob(jpeg_store + "2*lb%.jpg"))

        if len(imgnames) == 0:
            lock.release()
            print("No files to transfer: sleeping")
            sleep(60)
            continue

        #   Find all candidates... would be more efficient just to find the first

        candidates = [x for x in imgnames if "local" not in x]

        if 0 == len(candidates):
            lock.release()
            print("No files to transfer: sleeping")
            sleep(60)
            continue
        if debug:
            print("There are ", len(candidates), " files to transmit")

        outname = candidates[-1]

        if debug:
            print("Attempt to transmit:", outname)

        retransmissionActive.value += 1  # Watchdog

        scp_status = transfer.send_file(outname, user, hostname, remote_path)

        #       send_file may take a while, ensure despite this we are known to be active

        retransmissionActive.value += 1  # Watchdog
        if debug:
            print("Attempt to transmit:", outname, " status ", scp_status)

        #   If we succeed then rename the file as local... implying it also exists remotely

        if scp_status:
            newname = filenames.add_in_local_to_filename(
                number_pictures, outname, False
            )

            if newname != "":
                try:
                    os.rename(outname, newname)
                    os.system("touch " + newname)  # if inotify is watching prod it
                    if debug:
                        print("File renamed from", outname, " to ", newname)
                except Exception as err:
                    print(err)
            else:
                print("Rename failed for file", outname)

            lock.release()
        else:
            retransmissionActive.value += 1  # Watchdog
            lock.release()
            if debug:
                print("re_transmit failed ")


def send(user, hostname, final_dest, remote_path):
    filestore_lock = multiprocessing.Lock()
    re_transmit(filestore_lock, user, hostname, final_dest, remote_path)


if __name__ == "__main__":
    we_are = sys.argv.pop(0)
    inputargs = sys.argv

    if len(inputargs) != 4:
        print(
            we_are,
            "error: calling sequence should be user hostname local_destination remote_path",
        )
        sys.exit()

    if len(inputargs) == 4:
        user = inputargs[0]
        hostname = inputargs[1]
        final_dest = inputargs[2]
        remote_path = inputargs[3]
        send(user, hostname, final_dest, remote_path)
