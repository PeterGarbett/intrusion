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
import daytime
import crop
import trigger_external
import transfer

node = 1
version = 1.0
sshKeyLoc = ""  # should be .ssh and read from intrusion.conf

high_def = None

# Local filestore

jpeg_store = ""

SuppressDeletion = False  # True     # Dry run for test purposes
LocalSizeLimit = 1 * 2**30  # bytes required free
number_pictures = False  # Good for debugging, as an alternative to timestamps

# Remote filestore

user = ""
hostname = ""
path = ""

sleepDelay = 1.0  # Time to look away after a motion detect to avoid overloads
FRAME_CYCLE = 1024

# Avoid generating massive queues

frameLimit = 15
frameDelay = 3

# Subprocess rate limiting

window = 0.25  # analysis polling rate limiter
window2 = 0.1  # filestore management polling rate limiter
window3 = 6  # re_transmit polling rate


video_source = ""

#
#   Watchdog variables for sub-processes
#

framesBeingProcessed = multiprocessing.Value("i", 0)
yoloAnalysisActive = multiprocessing.Value("i", 0)
filestoreActive = multiprocessing.Value("i", 0)
retransmissionActive = multiprocessing.Value("i", 0)

sensitivityChange = multiprocessing.Value("f", 0)
sensitivity_upper = multiprocessing.Value("f", 0)
sensitivity_lower = multiprocessing.Value("f", 0)
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
    global sleepDelay
    global number_pictures
    global high_def
    global newKeyDir
    global sshKeyLoc
    global lifeforms
    global video_source
    global node

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
    if exl:
        config_found = trial_location
    else:
        exl = readfile_ignore_comments.readfile_ignore_comments(trial_location2, 0)
        if exl:
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

    high_def_bool_txt = load_param(exl, "high_def:")
    if high_def_bool_txt == "true":
        high_def = True
    else:
        high_def = False
        if high_def_bool_txt != "false":
            print("Bad selection value for high definition: assummed false")

    jpeg_store = load_param(exl, "local_filestore:")

    use_ts = load_param(exl, "use_timestamps:")
    if use_ts == "true":
        number_pictures = False
    else:
        if use_ts == "false":
            number_pictures = True
        else:
            print("Illegal timestamp selection - defaulting to timestamping")
            number_pictures = False

    ident_string = load_param(exl, "ident:")

    try:
        node = int(ident_string)
    except:
        print("Illegal value for system ident integer", ident_string)
        sys.exit()

    trigger_string = load_param(exl, "motion_trigger_initial:")

    try:
        sensitivityChange.value = float(trigger_string)
    except:
        print("Illegal value for trigger", trigger_string)
        sys.exit()

    trigger_string = load_param(exl, "motion_trigger_upper:")

    try:
        sensitivity_upper.value = float(trigger_string)
    except:
        print("Illegal value for trigger upper bound", trigger_string)
        sys.exit()

    trigger_string = load_param(exl, "motion_trigger_lower:")

    try:
        sensitivity_lower.value = float(trigger_string)
    except:
        print("Illegal value for trigger lower bound ", trigger_string)
        sys.exit()

    video_source = load_param(exl, "video_source:")

    sleep_delay_text = load_param(exl, "triggerdelay:")

    try:
        sleepDelay = float(sleep_delay_text)
    except:
        print("Illegal value for trigger delay,defaulting to 1.0:", sleep_delay_text)
        sleepDelay = 1.0

    # Look for new .ssh directory content

    sshKeyLoc = load_param(exl, "ssh_directory:")
    if sshKeyLoc != "":
        newKeyDir = load_param(exl, "new_ssh_elements:")
        if newKeyDir is not None:
            copy_ssh_keys.update_keys(newKeyDir, sshKeyLoc)

    #
    #   Not a lot of error checking for this one...
    #
    #
    lifeforms_text = load_param(exl, "lookfor:")
    lifeforms_ta = lifeforms_text.replace("]", "")
    lifeforms_tb = lifeforms_ta.replace("[", "")
    lifeformsc = lifeforms_tb.replace("'", "")
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
        print("Trigger:", sensitivityChange.value)
        print("TriggerDelayTime(secs):", sleepDelay)
        print("LookFor:", lifeforms)
        print("Remote hostname", hostname)
        print("Remote user:", user)
        print("Remote path", path)
        print("HD selected:", high_def)
        print("Local image storage:", jpeg_store)
        print("Use timestamps:", not number_pictures)
        print(".ssh directory :", sshKeyLoc)
        print("New .ssh directory contents:", newKeyDir)


#   Simple, lightweight
#   difference consequtive images and sum the pixel values
#   see if this exceeds a threshold


# Set initial time to expire timer immediatly

live_image_time_saved = datetime.datetime.now() - datetime.timedelta(minutes=70)

# This is to save the "testSnapshot.jpg" image at reasonable intervals
# Which bypasses the normal pipeline


def directly_save_image(webcam_file, frame, lock):
    """Save this image ito the filestore without it going via motion detection and yolo"""
    global live_image_time_saved

    acq = lock.acquire(block=False)  # Do this if we can but don't get in the way

    if acq:
        time_expired = (
            datetime.timedelta(minutes=60)
            < datetime.datetime.now() - live_image_time_saved
        )
        if time_expired:
            # Convert to RGB

            cols = cv.cvtColor(frame, cv.COLOR_BGR2RGB)

            # Convert to image

            image = im.fromarray(cols)

            # Save locally

            image.save(webcam_file)

            # Send elsewhere
            transfer.send_file(webcam_file, user, hostname, path)

            # Record when

            live_image_time_saved = datetime.datetime.now()
        lock.release()


def clamp(value, minn, maxn):
    """Clamp a value between limits"""
    value = minn if value <= minn else maxn if maxn <= value else value
    return value


def generate(yolo_process_q, lock):
    """Generate some images and pass on the ones that show motion"""
    global video_source
    # Some configuration values

    debug = False

    sensitivity = 0
    trigger = 0

    webcam_file = jpeg_store + "testSnapshot" + "_lb" + str(node) + ".jpg"

    if high_def:
        width = 1920
        height = 1080
    else:
        width = 640
        height = 480

    print("Configuration values :")
    print("Video Source:", video_source)
    print("Node ", node, "software version", version)
    print("TriggerDelayTime(secs):", sleepDelay)
    print("LookFor:", lifeforms)
    print("Remote hostname", hostname)
    print("Remote user:", user)
    print("Remote path", path)
    print("HD selected:", high_def)
    print("Local image storage:", jpeg_store)
    print("Use timestamps:", not number_pictures)
    print("New .ssh directory contents:", newKeyDir)
    print(".ssh directory :", sshKeyLoc)
    print("Trigger initial value:", sensitivityChange.value)
    print("Trigger upper bound:", sensitivity_upper.value)
    print("Trigger lower bound:", sensitivity_lower.value)

    sys.stdout.flush()  # Make sure we see the above immediatly in the systemd log

    # "sort of" live output`

    print("Unconditional periodic output on :", webcam_file)

    upper_trigger_limit = sensitivity_upper.value
    lower_trigger_limit = sensitivity_lower.value

    divisions = (upper_trigger_limit - lower_trigger_limit) / 50.0

    #   Setup video capture
    #   video_source is defined in the config file

    cap = cv.VideoCapture(video_source)
    if not cap.isOpened():
        print("Cannot open video source ")
        sys.exit()

    cap.set(3, width)
    cap.set(4, height)
    cap.set(6, cv.VideoWriter.fourcc("M", "J", "P", "G"))

    frame_count = 0
    detected = 0
    rejected = 0

    # video frame capture loop

    first = True

    #
    #   Need to make these defined by the config file
    #

    daycrop = None  # (750, 750 + 640, 400, 400 + 480)
    nightcrop = (450, 1400, 480, 980)
    location = (52.4823, -1.898575)  # Birmingham UK
    trigger = sensitivityChange.value

    light = daytime.daytime(location)

    fgbg = cv.bgsegm.createBackgroundSubtractorMOG()

    while True:
        # Read two images with a gap between to improve reliability of
        # motion detection. Should really be some sort of critical section

        ret, frame = cap.read()
        frame1 = crop.crop(frame, light, daycrop, nightcrop)

        #   Something like 10 percent of all the pixels
        #   Changed to be changed pixels. hopefully less dependent on brightness

        if first:
            pixel_diff_threshold = (
                128 * frame1.shape[0] * frame1.shape[1] * trigger / 100
            )
            first = False

        # if frame is read correctly ret is True
        if not ret:
            print("Can't receive frame (stream end?). Exiting ...")
            sleep(60)  # Allow yolo to catch up
            cap.release()
            break  # Result in child terminating and tripping of watchdog

        sleep(0.2)  # This might need changing or putting in config

        ret, frame = cap.read()
        frame2 = crop.crop(frame, light, daycrop, nightcrop)

        # if frame is read correctly ret is True
        if not ret:
            print("Can't receive frame (stream end?). Exiting ...")
            sleep(60)  # Allow yolo to catch up
            cap.release()
            break  # Result in child terminating and tripping of watchdog

        if frame_count == 0:  # Only check on this at a slowish rate
            directly_save_image(webcam_file, frame1, lock)
            if 0 == detected:
                trigger_external.low_event_count()

        #   Periodically assess effectiveness of trigger level
        #   at a sub-period of the frame rate

        if frame_count != 0 and 0 == frame_count % ((FRAME_CYCLE / 8) - 1):
            power_ratio = detected / (detected + rejected)

            sensitivity = 0  # Default : Leave alone

            if abs(power_ratio - 1.0) < 0.95:  # Want about 5%
                sensitivity = -1
            else:
                if abs(power_ratio) < 0.04:  # few candidates
                    sensitivity = 1

            if debug:
                print("Sensitivity:", sensitivity, " ratio:", power_ratio)

            trigger = sensitivityChange.value

            if debug:
                print("trigger:", trigger)

            trigger = trigger - sensitivity * divisions
            trigger = clamp(trigger, lower_trigger_limit, upper_trigger_limit)

            # Reset for next sampling period

            detected = 0
            rejected = 1

            if debug:
                print("trigger:", trigger)

            # Recalculate pixel threshold on changed trigger

            pixel_diff_threshold = (
                128 * frame1.shape[0] * frame1.shape[1] * trigger / 100
            )

            sensitivityChange.value = trigger

            if debug:
                print("Trigger value :", trigger, detected, rejected)

            # Dark or light ?

            light = daytime.daytime(location)

        frame_count += 1
        frame_count = frame_count % FRAME_CYCLE

        framesBeingProcessed.value += 1  # Update watchdog

        if debug:
            print("framesBeingProcessed set:", framesBeingProcessed.value)

        gray1 = cv.cvtColor(frame1, cv.COLOR_BGR2GRAY)
        gray2 = cv.cvtColor(frame2, cv.COLOR_BGR2GRAY)

        # difference = cv.absdiff(gray1, gray2)
        difference = fgbg.apply(gray2)
        # Calculate changed pixels with account taken for their change in value
        num_diff = np.sum(difference)

        if debug:
            num_diff_nonzero = cv.countNonZero(difference)
            print(
                pixel_diff_threshold,
                num_diff,
                num_diff_nonzero,
                pixel_diff_threshold < abs(num_diff),
            )

        if pixel_diff_threshold < abs(num_diff):
            timestamp = filenames.time_stamped_filename()
            qitem = (frame2, timestamp)
            yolo_process_q.put(qitem)

            # Trigger optional external actions

            trigger_external.motion_detected(light)
            directly_save_image(
                webcam_file, frame2, lock
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


def lifeforms_scan(frame, lifeforms):
    """

    Possible lifeforms this will detect are:
       {"person","bear","bird","cat", "cow","dog","elephant","giraffe", "horse", "sheep","zebra",}

    Some of these are rather unlikely
    given where we live

    You can also put car or truck in here...

    Detect whats in the image using yolo


    """

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

    return found_lifeforms


#   Filename to log performance data


performance_log_file = ""


def analyse(yolo_process_q, file_save_q):
    """

    Get image from queue 'yolo_process_q'
    Analyse image using yolo
    If it is interesting put it on queue 'file_save_q'

    """

    global performance_log_file
    global lifeforms

    debug = False
    rejects = 0
    found_someone = 0

    yolo.initialise_yolo()

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

        # Decompose

        item = frame_and_stamp[0]
        stamp = frame_and_stamp[1]

        if debug:
            print("analyse image")

        #   Yolo is done in grayscale so no point in doing RGB
        #   if we don't have too

        discovered = lifeforms_scan(item, lifeforms)
        if discovered:
            file_save_q.put((item, stamp, discovered))
            trigger_external.person_detected()
            found_someone += 1
            if debug:
                print("Lifeforms exist!")
        else:
            rejects += 1
            if debug:
                print("No lifeforms!!")

        if FRAME_CYCLE <= framesBeingProcessed.value:
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


def preserve(file_save_q, lock):
    """

    Stage 3 of our image pipeline. We have something worth saving
    so set about keeping it.

    """

    log_file = ""

    debug = False
    output_reason_file_was_saved = True

    frame_count = 0

    while True:
        filestoreActive.value += 1

        try:
            frame_and_stamp = file_save_q.get_nowait()
        except queue.Empty:
            sleep(window2)
            continue

        frame = cv.cvtColor(frame_and_stamp[0], cv.COLOR_BGR2RGB)
        image = im.fromarray(frame)
        timestamp = frame_and_stamp[1]
        whats_in_image = frame_and_stamp[2]

        if output_reason_file_was_saved:
            if log_file == "":
                log_file = (
                    jpeg_store
                    + "log_file_"
                    + filenames.time_stamped_filename()
                    + ".txt"
                )

            try:
                with open(log_file, "a+", encoding="ascii") as log:
                    log.write(timestamp + " discovered " + str(whats_in_image) + "\n")
            except Exception as err:
                print(err)

        outname = filenames.image_name(
            number_pictures, jpeg_store, node, frame_count, timestamp, False
        )

        if debug:
            print("Save image:", outname)

        #   Save file locally

        lock.acquire(block=True)
        image.save(outname)

        #   Try to send over the internet

        scp_status = transfer.send_file(outname, user, hostname, path)

        #   If we succeed then rename the file as local... implying it also exists remotely
        #   This means we can easily identify what hasn't been sent ...  to retry later

        if scp_status:
            newname = filenames.image_name(
                number_pictures, jpeg_store, node, frame_count, timestamp, True
            )
            os.rename(outname, newname)
            os.system("touch " + newname)  # if inotify is watching prod it
            if debug:
                print("File renamed from", outname, " to ", newname)
        else:
            if debug:
                print("file failed to copy to remote")

        frame_count += 1
        frame_count = (
            frame_count % FRAME_CYCLE
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

    debug = True

    while True:
        retransmissionActive.value += 1  # Watchdog
        sleep(window3)  # Whose update rate is low: beware
        retransmissionActive.value += 1  # Watchdog

        test_hostname = "google.com"  # example
        response = os.system("ping -c 1 -w2 " + test_hostname + " > /dev/null 2>&1")

        if response != 0:
            if debug:
                print("File transmission not possible, no internet connection")
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
        if debug:
            print("There are ", len(candidates), " files to transmit")

        outname = candidates[0]

        if debug:
            print("Attempt to transmit:", outname)

        retransmissionActive.value += 1  # Watchdog
        scp_status = transfer.send_file(outname, user, hostname, path)

        #       send_file may take a while, ensure despite this we are known to be active

        retransmissionActive.value += 1  # Watchdog
        if debug:
            print("Attempt to re_transmit:", outname, " status ", scp_status)

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


#
#   And now the multitasking bit....
#

# Attempt orderly shutdown


def signal_handler(signum, frame):
    """Catch termination signal so we can kill our children... yes really"""
    signame = signal.Signals(signum).name
    print("Caught signal", signame)

    for process in multiprocessing.active_children():
        process.terminate()

    sys.exit()


filestore_lock = multiprocessing.Lock()

# 	Routines used to parse configuration file


def find_element_substring(items, subst):
    """Is subst in a string somewhere in list of items ?"""
    for index in range(len(items)):
        if subst in items[index]:
            return index
    return -1


def load_param(exl, parameter):
    """Extract string defining parameter from the list.. if possible"""
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

    configure()

    trigger_external.initialise_trigger()

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
        name="MotionDetect", target=generate, args=(yolo_process_q, filestore_lock)
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
            filestore_lock,
        ),
    )

    process_4 = Process(name="remoteCopy", target=re_transmit, args=(filestore_lock,))

    # Start processes

    process_1.start()
    process_2.start()
    process_3.start()
    process_4.start()

    signal.signal(signal.SIGTERM, signal_handler)

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

        sleep(11 * window3 + 1)  # Wait for processes to increment it, if active

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
            print("loop count for reTransmission activity:", retransmissionActive.value)

            for process in multiprocessing.active_children():
                process.terminate()

    #   These processes never terminate under normal operation


if __name__ == "__main__":
    main()
