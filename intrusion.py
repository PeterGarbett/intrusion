"""

#
# 	Intrusion detection
#
#
#   Motion detector followed by using yolo to see if
#   given catagories are involved then saving of images
#   via scp - potentialy anywhere. Motion detection by itself
#   is prone to many false alarms when looking for people
#   with changing light and wind moving trees etc
#
#   Multiple tasks used, 3 main in image pipeline
#   This enables access to multiple cores.
#
# 		 q          file_save_q
# 	generate -> analyse -> preserve
#
# 	Generate
# 	produces images from camera and does basic motion detection
# 	then passes  images with motion detected into queue "q"
#
# 	analyse
# 	Subjects image to yolo (You Only look Once) to see
# 	if it contains objects of interest (as defined in configuration file
#
# 	preserve
# 	saves file to filesystem and attempts transfer via scp
# 	manages space if we are running out by deleting oldest files
# 	renames file to local_ if transfer suceeeds. It should be possfile_save_qle
#   to daisy chain several devices together.
#
# 	re_transmit
# 	Try to send file again and rename with prefix 'local_' on success.
#
# 	Last two processes share access using a filesystem lock
#
# 	main code gets configuration values, defines queues, sets
# 	off processes then checks they are alive at intervals.
# 	Restart in case of error. The service file should restart
# 	the program.
#
# 	queue exhaustion is avoided by rate limitimg image generation.
# 	There should be a large swapspace set up which will result in
# 	slowdown but not error if this calculation is transiently incorrect.
#
# 	Multiple values can be changed via a configuration file.
# 	The main process calls these and then sets off the processes
# 	Some of these parameters therefore have to be global but the
# 	ammount they are shared is actually minimal

"""

import multiprocessing
from multiprocessing import Process
from multiprocessing import Queue

# from multiprocessing import Value
# from multiprocessing import Pool
# from multiprocessing import active_children

import queue
from time import sleep
import datetime

import sys
import glob
import os
import signal

import cv2 as cv
import numpy as np
import paramiko

# from paramiko import SSHClient
from PIL import Image as im
from scp import SCPClient

import copy_ssh_keys
import yolo
import readfile_ignore_comments
import filenames
import manage_storage

node = 1
version = 1.0
sshKeyLoc = ""  # should be .ssh and read from intrusion.conf

high_def = None

# Local filestore

jpeg_store = ""

SuppressDeletion = False  # True     # Dry run for test purposes
LocalSizeLimit = 1 * 2 ** 30  # bytes required free
NumberPics = False  # Good for debugging, as an alternative to timestamps

# Remote filestore

user = ""
hostname = ""
path = ""

Trigger = 5  # Roughly, the percentage change that triggers a snapshot
sleepDelay = 1.0  # Time to look away after a motion detect to avoid overloads
frame_cycle = 1024

# Avoid generating massive queues

frameLimit = 15
frameDelay = 3

# Subprocess rate limiting

window = 0.25  # analysis polling rate limiter
window2 = 0.1  # filestore management polling rate limiter
window3 = 60  # re_transmit polling rate

#
#   Watchdog variables for sub-processes
#

framesBeingProcessed = multiprocessing.Value("i", 0)
yoloAnalysisActive = multiprocessing.Value("i", 0)
filestoreActive = multiprocessing.Value("i", 0)
retransmissionActive = multiprocessing.Value("i", 0)
sensitivityChange = multiprocessing.Value("f", 0)

#
# 	Load a few variables from our configuration file
#
#
#
#


def configure():
    # These variables are in the same global scope as main so multiprocessing aspects don't arise

    global user
    global hostname
    global path
    global jpeg_store
    global Trigger
    global sleepDelay
    global numberPics
    global high_def
    global newKeyDir
    global sshKeyLoc
    global lifeforms

    debug = False

    #   Search directories for intrusion.conf

    config_filename = "intrusion.conf"
    config_location = "/exdrive/Snapshots/"
    config_location2 = "/etc/intrusion/"

    #   It is important to select no change of case here since some data are file locations

    config_found = ""
    trial_location = config_location + config_filename
    trial_location2 = config_location2 + config_filename

    exl = readfile_ignore_comments.readfile_ignore_comments(trial_location, 0)
    if [] != exl:
        config_found = trial_location
    else:
        exl = readfile_ignore_comments.readfile_ignore_comments(trial_location2, 0)
        if [] != exl:
            config_found = trial_location2

    if config_found == "":
        print(
            "No configuration file found,need", trial_location, " or ", trial_location2
        )
        sys.exit()
    else:
        print("Using configuration file ", config_found)

    user = user + load_param(exl, "remote_user:")
    hostname = hostname + load_param(exl, "remote_url:")
    path = path + load_param(exl, "remote_path:")

    hd = load_param(exl, "high_def:")
    if hd == "true":
        high_def = True
    else:
        high_def = False
        if hd != "false":
            print("Bad selection value for high definition: assummed false")

    jpeg_store = load_param(exl, "local_filestore:")

    useTS = load_param(exl, "use_timestamps:")
    if useTS == "true":
        numberPics = False
    else:
        if useTS == "false":
            numberPics = True
        else:
            print("Illegal timestamp selection - defaulting to timestamping")
            numberPics = False

    triggerStr = load_param(exl, "motion_trigger_level:")

    try:
        Trigger = float(triggerStr)
    except:
        print("Illegal value for trigger", triggerStr)
        sys.exit()

    sleepDelayTxt = load_param(exl, "triggerdelay:")

    try:
        sleepDelay = float(sleepDelayTxt)
    except:
        print("Illegal value for trigger delay,defaulting to 1.0:", sleepDelayTxt)
        sleepDelay = 1.0

    # Look for new .ssh directory content

    sshKeyLoc = load_param(exl, "ssh_directory:")
    if sshKeyLoc != "":
        newKeyDir = load_param(exl, "new_ssh_elements:")
        if newKeyDir != None:
            copy_ssh_keys.update_keys(newKeyDir, sshKeyLoc)

    #
    #   Not a lot of error checking for this one...
    #
    #
    lifeformsText = load_param(exl, "lookfor:")
    lifeformsTa = lifeformsText.replace("]", "")
    lifeformsTb = lifeformsTa.replace("[", "")
    lifeformsc = lifeformsTb.replace("'", "")
    lifeforms = set(lifeformsc.split(","))

    #   Check filestore location exists

    try:
        os.listdir(jpeg_store)
    except:
        print("Directory", jpeg_store, "not found")
        sys.exit()

    debug = False

    if debug:
        print("Configuration values as read :")
        print("Trigger:", Trigger)
        sensitivityChange.value = Trigger
        print("TriggerDelayTime(secs):", sleepDelay)
        print("LookFor:", lifeforms)
        print("Remote hostname", hostname)
        print("Remote user:", user)
        print("Remote path", path)
        print("HD selected:", high_def)
        print("Local image storage:", jpeg_store)
        print("Use timestamps:", not numberPics)
        print(".ssh directory :", sshKeyLoc)
        print("New .ssh directory contents:", newKeyDir)


#   Simple, lightweight
#   difference consequtive images and sum the pixel values
#   see if this exceeds a threshold


# Set initial time to expire timer immediatly

live_image_time_saved = datetime.datetime.now() - datetime.timedelta(minutes=70)

# This is to save the "testSnapshot.jpg" image at reasonable intervals
# Which bypasses the normal pipeline


def directly_save_image(webcamFile, frame, lock):
    global live_image_time_saved

    acq = lock.acquire(block=False)  # Do this if we can but don't get in the way

    if acq:
        timeExpired = (
            datetime.timedelta(minutes=60)
            < datetime.datetime.now() - live_image_time_saved
        )
        if timeExpired:
            # Convert to RGB

            cols = cv.cvtColor(frame, cv.COLOR_BGR2RGB)

            # Convert to image

            image = im.fromarray(cols)

            # Save locally

            image.save(webcamFile)

            # Send elsewhere

            scp_status = send_file(webcamFile)

            # Record when

            live_image_time_saved = datetime.datetime.now()
        lock.release()


def clamp(n, minn, maxn):
    ''' Clamp a value between limits '''
    n = minn if n <= minn else maxn if maxn <= n else n
    return n


def generate(yolo_process_q, lock):
    global framePairCount
    global Trigger
    global frame_cycle

    # Some configuration values

    debug = False

    sensitivity = 0

    webcamFile = jpeg_store + "testSnapshot.jpg"

    if high_def:
        width = 1920
        height = 1080
    else:
        width = 640
        height = 480

    print("Configuration values :")
    print("Node ", node, "software version", version)
    sensitivityChange.value = Trigger
    print("Trigger:", sensitivityChange.value)
    print("TriggerDelayTime(secs):", sleepDelay)
    print("LookFor:", lifeforms)
    print("Remote hostname", hostname)
    print("Remote user:", user)
    print("Remote path", path)
    print("HD selected:", high_def)
    print("Local image storage:", jpeg_store)
    print("Use timestamps:", not numberPics)
    print("New .ssh directory contents:", newKeyDir)
    print(".ssh directory :", sshKeyLoc)

    sys.stdout.flush()  # Make sure we see the above immediatly in the systemd log

    # "sort of" live output`

    print("Live(ish) output on :", webcamFile)

    #   Something like 10 percent of all the pixels
    #   Changed to be changed pixels. hopefully less dependent on brightness

    PixelDiffThreshold = 128 * width * height * Trigger / 100

    #   Setup video capture
    #   the 0 lets opencv figure it out which it does nicely when there
    #   is only one camera

    cap = cv.VideoCapture(0)
    if not cap.isOpened():
        print("Cannot open camera")
        sys.exit()

    cap.set(3, width)
    cap.set(4, height)
    cap.set(6, cv.VideoWriter.fourcc("M", "J", "P", "G"))

    frame_count = 0
    detected = 0
    rejected = 0

    # video frame capture loop

    while True:
        # Read two images with a gap between to improve reliability of
        # motion detection. Should really be some sort of critical section

        ret, frame1 = cap.read()

        # if frame is read correctly ret is True
        if not ret:
            print("Can't receive frame (stream end?). Exiting ...")
            cap.release()
            break  # Result in child terminating and tripping of watchdog

        sleep(0.2)  # This might need changing or putting in config

        ret, frame2 = cap.read()

        # if frame is read correctly ret is True
        if not ret:
            print("Can't receive frame (stream end?). Exiting ...")
            cap.release()
            break  # Result in child terminating and tripping of watchdog

        if frame_count == 0:  # Only check on this at a slowish rate
            directly_save_image(webcamFile, frame1, lock)
        #        if frame_count != 0 and 0 == frame_count % (frame_cycle - 1):
        if frame_count != 0 and 0 == frame_count % (512 - 1):
            #   Assess effectiveness of trigger level
            power_ratio = detected / (detected + rejected)

            if abs(power_ratio - 1.0) < 0.95:  # Want about 5%
                sensitivity = -1
            else:
                if abs(power_ratio) < 0.01:  # Fewer than 1% show movement
                    sensitivity = 1
                else:
                    sensitivity = 0  # Leave alone
            if debug:
                print("Sensitivity:", sensitivity, " ratio:", power_ratio)
            lowTlimit = 2.0
            uppTlimit = 3.5
            divisions = (uppTlimit - lowTlimit) / 50.0
            if debug:
                print("trigger:", Trigger)
            Trigger = Trigger - sensitivity * divisions
            Trigger = clamp(Trigger, lowTlimit, uppTlimit)
            if debug:
                print("trigger:", Trigger)

            PixelDiffThreshold = 128 * width * height * Trigger / 100
            sensitivityChange.value = Trigger
            if debug:
                print("Trigger value :", Trigger, detected, rejected)
        frame_count += 1
        frame_count = frame_count % frame_cycle

        framesBeingProcessed.value += 1  # Update watchdog

        if debug:
            print("framesBeingProcessed set:", framesBeingProcessed.value)

        gray1 = cv.cvtColor(frame1, cv.COLOR_BGR2GRAY)
        gray2 = cv.cvtColor(frame2, cv.COLOR_BGR2GRAY)

        difference = cv.absdiff(gray1, gray2)
        # Calculate changed pixels with account taken for their change in value
        num_diff = np.sum(difference)

        if debug:
            num_diffNZ = cv.countNonZero(difference)
            print(
                PixelDiffThreshold,
                num_diff,
                num_diffNZ,
                PixelDiffThreshold < abs(num_diff),
            )

        if PixelDiffThreshold < abs(num_diff):
            timestamp = filenames.time_stamped_filename()
            qitem = (frame2, timestamp)
            yolo_process_q.put(qitem)
            directly_save_image(
                webcamFile, frame2, lock
            )  # Keep live image recent when changes occur
            if debug:
                print("Motion detected, pushed frame", frame_count)
            sleep(sleepDelay)
            while frameLimit < yolo_process_q.qsize():
                sleep(frameDelay)  # Prevent system overload
            detected += 1
        else:
            rejected += 1

        sleep(0.5)

    # When everything done, release the capture

    cap.release()

    sys.exit(0)


# Define a function that will run in a separate process


#
# Some of these are rather unlikely
# given where we live
#
# possfile_save_qle lifeforms yolo will detect are:
#    {"person","bear","bird","cat", "cow","dog","elephant","giraffe", "horse", "sheep","zebra",}
#
# You can also put car or truck in here...
#
# Detect whats in the image using yolo
#


def lifeforms_scan(frame):
    debug = False

    # Need an entry point that takes an image
    # Could scan for lots of things..
    # Full list in yolov3.txt
    # What we actually scan for is defined in the config file

    found = set(yolo.yolo_image(frame))
    found_lifeforms = found & lifeforms

    if debug:
        print("found:", found)
        print("lifeforms found:", found_lifeforms)

    if len(found_lifeforms) == 0:
        return False

    return True


#   Filename to log performance data

performance_log_file = ""


def analyse(yolo_process_q, file_save_q):
    """

    Get image from queue 'yolo_process_q'
    Analyse image using yolo
    If it is interesting put it on queue 'file_save_q'

    """

    rejects = 0
    found_someone = 0
    global Trigger
    global performance_log_file
    global frame_cycle

    debug = False

    if performance_log_file == "":
        performance_log_file = (
            jpeg_store
            + "performance_log_file_"
            + filenames.time_stamped_filename()
            + ".txt"
        )

    while True:
        yoloAnalysisActive.value += 1

        try:
            frame_and_stamp = yolo_process_q.get_nowait()
        except queue.Empty:
            sleep(window)
            continue

        item = frame_and_stamp[0]

        if debug:
            print("analyse image")

        #   Yolo is done in grayscale so no point in doing RGB
        #   if we don't have too

        if lifeforms_scan(item):
            file_save_q.put(frame_and_stamp)
            found_someone += 1
            if debug:
                print("Lifeforms exist!")
        else:
            rejects += 1
            if debug:
                print("No lifeforms!!")

        if frame_cycle <= framesBeingProcessed.value:
            try:
                with open(performance_log_file, "a+", encoding="ascii") as perf_log:
                    perf_log.write(
                        str(datetime.datetime.now())
                        + ": Trigger level:"
                        + str(sensitivityChange.value)
                        + "\nFrame pairs:"
                        + str(framesBeingProcessed.value)
                        + " Frames with motion:"
                        + str(rejects + found_someone)
                        + " Frames with people:"
                        + str(found_someone)
                        + "\nFrames queued to analyse "
                        + str(yolo_process_q.qsize())
                        + " Frames queued to save:"
                        + str(file_save_q.qsize())
                        + "\n"
                    )
                    print("Performance data written on ", performance_log_file)
                    framesBeingProcessed.value = 0
                    rejects = 0
                    found_someone = 0
            except Exception as err:
                print(err)


# Send image to somewhere non-local using scp
# This could be anywhere on the internet


def send_file(filename):
    debug = False

    sent = True

    try:
        if debug:
            print("scp file")
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.connect(hostname, username=user)
        with SCPClient(client.get_transport()) as scp:
            scp.put(filename, remote_path=path)
    except Exception as err:
        if debug:
            print("Failed to save file to remote", err)
        sent = False

    return sent




def preserve(file_save_q, lock):
    """

    Stage 3 of our image pipeline. We have something worth saving
    so set about keeping it.

    """

    debug = False

    frame_count = 0

    while True:
        filestoreActive.value += 1

        try:
            frame_and_stamp = file_save_q.get_nowait()
        except queue.Empty:
            sleep(window2)
            continue

        frame = cv.cvtColor(frame_and_stamp[0], cv.COLOR_BGR2RGB)
        timestamp = frame_and_stamp[1]
        image = im.fromarray(frame)

        outname = filenames.image_name(
            NumberPics, jpeg_store, node, frame_count, timestamp, False
        )

        if debug:
            print("Save image", outname)

        #   Save file locally

        lock.acquire(block=True)
        image.save(outname)

        #   Try to send over the internet

        scp_status = send_file(outname)

        #   If we succeed then rename the file as local... implying it also exists remotely
        #   This means we can easily identify what hasn't been sent ...  to retry later

        if scp_status:
            newname = filenames.image_name(
                NumberPics, jpeg_store, node, frame_count, timestamp, True
            )
            os.system("touch " + newname)  # if inotify is watching prod it
            os.rename(outname, newname)
            if debug:
                print("File renamed from", outname, " to ", newname)
        else:
            if debug:
                print("file failed to copy to remote")

        frame_count += 1
        frame_count = (
            frame_count % frame_cycle
        )  # Make these wrap around so they don't used unbounded levels of storage

        lock.release()


def re_transmit(lock):
    """
    re_transmit - which is in fact a misnomer it's more like retry
    transferring something that didn't go the first time.
    This is intended to be a background task and would come into play
    if the connection to the remote machine went down transiently
    I assumme here we aren't sending data out to a machine on the LAN
    the main case of interest is lost internet, so we test for it
    working 1st
    """

    debug = False

    while True:
        retransmissionActive.value += 1  # Watchdog
        sleep(window3)  # Whose update rate is low: beware

        hostname = "google.com"  # example
        response = os.system("ping -c 1 -w2 " + hostname + " > /dev/null 2>&1")

        if response != 0:
            if debug:
                print("No internet connection")
            continue

        acq = lock.acquire(block=False)
        if not acq:
            continue

        manage_storage.make_space(
            jpeg_store, LocalSizeLimit
        )  # Check filesystem size and delete if necessary

        # get candidate image files (excluding live)
        # This only works well with timestamped files

        imgnames = sorted(glob.glob(jpeg_store + "2*.jpg"))

        if len(imgnames) == 0:
            lock.release()
            continue

        #   Find all candidates... would be more efficient just to find the first

        candidates = [x for x in imgnames if "local" not in x]

        if 0 == len(candidates):
            lock.release()
            continue
        outname = candidates[0]

        if debug:
            print("re_transmit:", outname)

        scp_status = send_file(outname)

        #   If we succeed then rename the file as local... implying it also exists remotely

        if scp_status:
            newname = filenames.add_in_local_to_filename(NumberPics, outname, False)

            if newname != "":
                os.system("touch " + newname)  # if inotify is watching prod it
                os.rename(outname, newname)
                if debug:
                    print("File renamed from", outname, " to ", newname)
        else:
            sleep(1024)

        lock.release()


#
#   And now the multitasking bit....
#

# Attempt orderly shutdown


def handler(signum):
    """Catch termination signal so we can kill our children... yes really"""
    signame = signal.Signals(signum).name
    print("Caught signal", signame)

    for process in multiprocessing.active_children():
        process.terminate()

    sys.exit()


fileLock = multiprocessing.Lock()


# 	Routines used to parse configuration file


def find_element_substring(items, subst):
    for index in range(len(items)):
        if subst in items[index]:
            return index
    return -1


def load_param(exl, parameter):
    index = find_element_substring(exl, parameter)
    if index == -1:
        print(parameter, "not defined in config file")
        sys.exit()
    else:
        filestr = exl[index]
        filestr = filestr.split(":")
        data = filestr[1]

        return data


def main():
    """setup processes, start and monitor them"""
    global cap

    configure()

    #   Configuration complete. Now start

    debug = False

    # parent = multiprocessing.parent_process()
    parent_pid = 0  # parent.pid

    expected_children = 4

    # The following code sets up the queues and processes and starts them
    #
    # we have three processes connectd by two queues namely
    # generate->q->analyse->file_save_q->preserve  and a re_transmit background task
    # which  shares a filesystem lock with preserve

    # Create an instance of the Queue class

    yolo_process_q = Queue()
    file_save_q = Queue()

    # Create instances of the Process class, one for each function

    process_1 = Process(
        name="MotionDetect", target=generate, args=(yolo_process_q, fileLock)
    )

    process_2 = Process(
        name="yoloFilter",
        target=analyse,
        args=(
            yolo_process_q,
            file_save_q,
        ),
    )

    process_3 = Process(
        name="fileStore",
        target=preserve,
        args=(
            file_save_q,
            fileLock,
        ),
    )

    process_4 = Process(name="remoteCopy", target=re_transmit, args=(fileLock,))

    # Start processes

    process_1.start()
    process_2.start()
    process_3.start()
    process_4.start()

    signal.signal(signal.SIGTERM, handler)

    if debug:
        print(
            "PIDs",
            parent_pid,
            process_1.pid,
            process_2.pid,
            process_3.pid,
            process_4.pid,
        )

    #   Watchdog

    framesBeingProcessed.value = 0

    while True:

        # Check children are all (nominally) active

        child_count = 0
        for process in multiprocessing.active_children():
            child_count += 1
        if debug:
            print("Active children", child_count)
        if child_count < expected_children:
            print("A Child has gone missing")
            for process in multiprocessing.active_children():
                print("Active child:", process)
                process.terminate()
            sys.exit()

        # Inspect a pulse for each process

        saved_frame_count = framesBeingProcessed.value
        yoloAnalysisActive.value = 0
        filestoreActive.value = 0
        retransmissionActive.value = 0  # Check this at a slower rate

        #       In fact check everything at quite a slow rate

        sleep(10 * window3 + 1)  # Wait for processes to increment it, if active

        if debug:
            print("loop count for generate:", framesBeingProcessed.value)
            print("loop count for yolo analysis:", yoloAnalysisActive.value)
            print("loop count for filestore handling:", filestoreActive.value)
            print(
                "loop count for reTransmission activity:", retransmissionActive.value
            )  # Check this at a slower rate

        if (
            framesBeingProcessed.value == saved_frame_count
            or yoloAnalysisActive.value == 0
            or filestoreActive.value == 0
            or retransmissionActive.value == 0
        ):
            print("Processing has stopped, exit anticipating a systemd restart")
            print("loop count for frame generate:", framesBeingProcessed.value)
            print("loop count for yolo analysis:", yoloAnalysisActive.value)
            print("loop count for filestore handling:", filestoreActive.value)
            print("loop count for reTramission activity:", retransmissionActive.value)

            for process in multiprocessing.active_children():
                process.terminate()

    #   These processes never terminate under normal operation


if __name__ == "__main__":
    """Routine entry point"""
    main()
