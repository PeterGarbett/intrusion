"""

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

"""

import sys
import argparse
import cv2
import numpy as np


def start(image_file_name, direct_image, use_direct):
    """

    emulates what the software would expect for the command line.
    I've chosen /etc/opt/yolo as a home for the data files. This file
    on /usr/local/bin so I can call it froum anywhere

    """

    args = argparse.Namespace(
        image=image_file_name,
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

    if use_direct:
        image = direct_image
    else:
        try:
            image = cv2.imread(args.image)
        except:
            print("Image file ", args.image, "not found")
            sys.exit()

    try:
        image_width = image.shape[1]
        image_height = image.shape[0]
    except:
        return []

    scale = 0.00392
    classes = None

    with open(args.classes, "r", encoding="ascii") as class_file:
        classes = [line.strip() for line in class_file.readlines()]

    # COLORS = np.random.uniform(0, 255, size=(len(classes), 3))

    net = cv2.dnn.readNet(args.weights, args.config)

    blob = cv2.dnn.blobFromImage(image, scale, (416, 416), (0, 0, 0), True, crop=False)

    net.setInput(blob)

    outs = net.forward(get_output_layers(net))

    # I don't actually uses these boxes at the moment  but they might be useful later

    class_ids = []
    confidences = []
    boxes = []
    conf_threshold = 0.5

    for out in outs:
        for detection in out:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            if confidence > conf_threshold:
                center_x = int(detection[0] * image_width)
                center_y = int(detection[1] * image_height)
                box_width = int(detection[2] * image_width)
                box_height = int(detection[3] * image_height)
                box_x_coordinate = center_x - box_width / 2
                box_y_coordinate = center_y - box_height / 2
                class_ids.append(class_id)
                confidences.append(float(confidence))
                boxes.append(
                    [box_x_coordinate, box_y_coordinate, box_width, box_height]
                )

    items = list(set(class_ids))
    names = [str(classes[x]) for x in items]

    return names


def yolo_image(image):
    """Entry point for function to apply yolo to an image returning a list of found items"""
    items = start(None, image, True)
    return items


def yolo_file(filename):
    """Entry point for function to apply yolo to a file returning a list of found items"""
    items = start(filename, None, False)
    return items
