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


def yolo(image):
    """use yolo on an image"""
    global net

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
    items = yolo(image)
    return items


def yolo_file(file_name):
    """Use yolo on an image file and return what is found"""
    image = cv2.imread(file_name)
    items = yolo(image)

    return items


if __name__ == "__main__":
    """Test by using the routines on images in the current directory"""

    imgnames = sorted(glob.glob("*.jpg"))

    initialise_yolo()

    for name in imgnames:
        types = yolo_file(name)
        if not "person" in types:
            print("no people in :", types, " in ", name)
