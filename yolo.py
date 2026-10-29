"""Interface to yolo26"""

import glob
import os
import sys
import time
import cv2
from ultralytics import YOLO


def initialise_yolo(version="/opt/yolo/yolo26n.pt"):
    """Setup what model to use"""
    global model
    model = YOLO(version)  # load an official model


def yolo_image_internal(image, threshold=0.8):
    """Use yolo on an image and return what is found"""
    global model

    # Predict with the model
    results = model(image, verbose=False)
    # Access the results (in fact should only be one)
    result = results[0]

    # For reference, this is how to extract these values...
    # but will be flgged as unused.

    #    xywh = result.boxes.xywh  # center-x, center-y, width, height
    #    xywhn = result.boxes.xywhn  # normalized
    #    xyxy = result.boxes.xyxy  # top-left-x, top-left-y, bottom-right-x, bottom-right-y
    #    xyxyn = result.boxes.xyxyn  # normalized

    names = [
        result.names[cls.item()] for cls in result.boxes.cls.int()
    ]  # class name of each box

    confs = result.boxes.conf  # confidence score of each box

    found = []

    for index, name in enumerate(names):
        if "person" == name:
            if threshold < confs[index].item():
                found.append(name)
        else:
            found.append(name)

    return (found, result)


def yolo_file(file_name, modify=True, threshold=0.0):
    """Use yolo on an image file and return what is found"""

    image = cv2.imread(file_name)
    start =time.perf_counter()
    (items, result) = yolo_image_internal(image, threshold)
    end =time.perf_counter()
    print(end-start)

    if modify and items:
        result.plot()
        result.save(filename=file_name)

    return items

def yolo_image(image, threshold=0.8):
    (items, result) = yolo_image_internal(image, threshold)
    return items

#
#   motion is lightweight but prone to false positives.
#   Search through the images and produce a script
#   that will remove those without items of interest.
#   The view here allways has cars in it. Your situation may well differ
#


#
# Detect whats in the image using yolo
#


def main():
    """Test by using the routines on image files"""

    lifeforms = {
        "person",
        "bear",
        "bird",
        "cat",
        "cow",
        "dog",
        "elephant",
        "giraffe",
        "horse",
        "sheep",
        "zebra",
    }

    #   Use specified base directory
    #   Should be writable so I can place a list
    #   of analysed items into it
    #   Defaults to  which means the current directory

    inputargs = sys.argv
    if inputargs:
        inputargs.pop(0)

    if len(inputargs) != 1:
        print("badly specified base directory, exiting")
        sys.exit()
    else:
        base_directory = inputargs[0]

    initialise_yolo()

    #   Output the script header

    print("#!/bin/bash")
    print("#")
    print("#\tScript to remove boring images")
    print("#")
    print("#\tBase directory:", base_directory)
    print("#")

    #   Pull out the previous results. This is important because yolo
    #   uses a fair ammount of resource so we avoid redoing things
    #   This is chosen to be saved as text for ease of inspection and test

    interesting = []
    try:
        with open(base_directory + "interesting.txt", "r", encoding="ascii") as file:
            for line in file:
                x = line.replace("\n", "")
                if x != "":
                    interesting.append(x)
            file.close()
    except:
        interesting = []

    imgnames = sorted(glob.glob(base_directory + "*.jpg"))

    all_items = {}

    for image_file in imgnames:
        decomp = os.path.basename(image_file)
        if decomp not in interesting:
            raw_found = set(yolo_file(decomp))
            found = raw_found & lifeforms

            if found:
                all_items = set(found).union(all_items)
                print("#", image_file, " ", list(all_items))
                interesting.append(os.path.basename(image_file))
            else:
                decomp = os.path.basename(image_file)
                print("rm -f ", decomp)

    # Write back list of items with interesting objects found in them

    try:
        with open(base_directory + "interesting.txt", "w", encoding="ascii") as file:
            file.write("\n".join(str(item) for item in interesting))
            file.close()
    except Exception as err:
        print("#", err)
        print("#Attempt to write file of interesting items locally\n")
        try:
            with open("./interesting.txt", "w", encoding="ascii") as file:
                file.write("\n".join(str(item) for item in interesting))
                file.close()
        except Exception as err2:
            print(err2)


if __name__ == "__main__":
    main()

