#############################################
# Object detection - YOLO - OpenCV
# Author : Arun Ponnusamy   (July 16, 2018)
# Website : http://www.arunponnusamy.com
############################################
#
# Hacked to return a list of types of objects found
# and entry points added to operate directly on a image
# or on a file containing an image.  Direct command line 
# usage removed and yolo file locations fixed
# at /etc/opt/yolo/
#

import cv2
import argparse
import numpy as np


def start(imageFileName, directImage, useDirect):


# This emulates what the software would expect for the command line.
# I've chosen /etc/opt/yolo as a home for the data files. This file
# on /usr/local/bin so I can call it froum anywhere

    args = argparse.Namespace(
        image=imageFileName,
        config="/etc/opt/yolo/yolov3.cfg",
        weights="/etc/opt/yolo/yolov3.weights",
        classes="/etc/opt/yolo/yolov3.txt",
    )

    def get_output_layers(net):

        layer_names = net.getLayerNames()
        try:
            output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]
        except:
            output_layers = [
                layer_names[i[0] - 1] for i in net.getUnconnectedOutLayers()
            ]

        return output_layers

    if useDirect:
        image = directImage
    else:
        try:
            image = cv2.imread(args.image)
        except:
            print("Image file ", args.image, "not found")
            exit()

    try:
        Width = image.shape[1]
        Height = image.shape[0]
    except:
        return []

    scale = 0.00392
    classes = None

    with open(args.classes, "r") as f:
        classes = [line.strip() for line in f.readlines()]

    COLORS = np.random.uniform(0, 255, size=(len(classes), 3))

    net = cv2.dnn.readNet(args.weights, args.config)

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

    items = list(set(class_ids))
    names = [str(classes[x]) for x in items]

    return names


def yoloImage(image):
    items = start(None, image, True)
    return items


def yoloFile(filename):

    items = start(filename, None, False)
    return items
