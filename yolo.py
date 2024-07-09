"""

#############################################
# Object detection - YOLO - OpenCV
# Author : Arun Ponnusamy   (July 16, 2018)
# Website : http://www.arunponnusamy.com
############################################

Hacked to interface to intrusion.py

"""

import cv2
import numpy as np
import glob

config = "/etc/opt/yolo/yolov3.cfg"
weights = "/etc/opt/yolo/yolov3.weights"
classes_file = "/etc/opt/yolo/yolov3.txt"


def initialise_yolo():
    """Separate out the file reading aspects to a once only read"""
    global classes
    global COLORS
    global net

    with open(classes_file, "r") as f:
        classes = [line.strip() for line in f.readlines()]
    COLORS = np.random.uniform(0, 255, size=(len(classes), 3))
    net = cv2.dnn.readNet(weights, config)


def yolo_analysis(image):
    """use yolo on an image"""
    global net

    # Protect from null arguments

    if image.any() == None:
        return []

    output_result_image = False

    def get_output_layers(net):
        layer_names = net.getLayerNames()
        try:
            output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]
        except:
            output_layers = [
                layer_names[i[0] - 1] for i in net.getUnconnectedOutLayers()
            ]

        return output_layers

    def draw_prediction(img, class_id, confidence, x, y, x_plus_w, y_plus_h):
        label = str(classes[class_id])
        color = COLORS[class_id]

        cv2.rectangle(img, (x, y), (x_plus_w, y_plus_h), color, 2)

        cv2.putText(
            img, label, (x - 10, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
        )

    Width = image.shape[1]
    Height = image.shape[0]
    scale = 0.00392

    blob = cv2.dnn.blobFromImage(image, scale, (416, 416), (0, 0, 0), True, crop=False)

    net.setInput(blob)

    outs = net.forward(get_output_layers(net))

    class_ids = []
    confidences = []
    boxes = []
    conf_threshold = 0.5
    nms_threshold = 0.4

    for out in outs:
        for detection in out:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            if confidence > 0.5:
                center_x = int(detection[0] * Width)
                center_y = int(detection[1] * Height)
                w = int(detection[2] * Width)
                h = int(detection[3] * Height)
                x = center_x - w / 2
                y = center_y - h / 2
                class_ids.append(class_id)
                confidences.append(float(confidence))
                boxes.append([x, y, w, h])

    indices = cv2.dnn.NMSBoxes(boxes, confidences, conf_threshold, nms_threshold)

    things = []
    for i in indices:
        things.append(classes[class_ids[i]])
    types = list(set(things))

    if output_result_image:
        for i in indices:
            try:
                box = boxes[i]
            except:
                i = i[0]
                box = boxes[i]

            x = box[0]
            y = box[1]
            w = box[2]
            h = box[3]
            draw_prediction(
                image,
                class_ids[i],
                confidences[i],
                round(x),
                round(y),
                round(x + w),
                round(y + h),
            )

        cv2.imwrite("object-detection.jpg", image)
        cv2.destroyAllWindows()

    return types


def yolo_image(image):
    """Use yolo on an image and return what is found"""

    items = yolo_analysis(image)
    return items


def yolo_file(file_name):
    """Use yolo on an image file and return what is found"""
    image = cv2.imread(file_name)
    items = yolo_analysis(image)

    return items


#
#   motion is lightweight but prone to false positives.
#   Search through the images and produce a script
#   that will remove those without items of interest.
#   The view here allways has cars in it. Your situation may well differ
#

import yolo
import glob
import os
import sys
import intrusion
import cv2

animated = {
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

#
# Detect whats in the image using yolo
#


def main():
    """Test by using the routines on image files"""

    #   Use specified base directory
    #   Should be writable so I can place a list
    #   of analysed items into it
    #   Defaults to "" which means the current directory

    inputargs = sys.argv
    sys.argv.pop(0)

    if len(inputargs) == 0:
        baseDirectory = ""
    else:
        if len(inputargs) != 1:
            print("badly specified base directory, exiting")
            exit()
        else:
            baseDirectory = inputargs[0]

    yolo.initialise_yolo()

    #   Output the script header

    print("#!/bin/bash")
    print("#")
    print("#\tScript to remove boring images")
    print("#")
    print("#\tBase directory:", baseDirectory)
    print("#")

    #   Pull out the previous results. This is important because yolo
    #   uses a fair ammount of resource so we avoid redoing things
    #   This is chosen to be saved as text for ease of inspection and test

    interesting = []
    try:
        with open(baseDirectory + "interesting.txt", "r") as file:
            for line in file:
                x = line.replace("\n", "")
                if x != "":
                    interesting.append(x)
            file.close()
    except:
        interesting = []

    imgnames = sorted(glob.glob(baseDirectory + "*.jpg"))

    allItems = {}

    for image_file in imgnames:
        decomp = os.path.basename(image_file)
        if decomp not in interesting:
            image = cv2.imread(image_file)
            found = intrusion.lifeforms_scan(image, animated)
            if found:
                allItems = set(found).union(allItems)
                print("#", image_file, " ", list(allItems))
                interesting.append(os.path.basename(image_file))
            else:
                decomp = os.path.basename(image_file)
                print("rm -f ", decomp)

    # Write back list of items with interesting objects found in them

    try:
        with open(baseDirectory + "interesting.txt", "w") as file:
            file.write("\n".join(str(item) for item in interesting))
            file.close()
    except Exception as err:
        print("#", err)
        print("#Attempt to write file of interesting items locally\n")
        try:
            with open("./interesting.txt", "w") as file:
                file.write("\n".join(str(item) for item in interesting))
                file.close()
        except Exception as err:
            print(err)


if __name__ == "__main__":
    main()
