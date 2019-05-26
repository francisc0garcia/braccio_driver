#!/usr/bin/env python3

import sys
import time

# numpy and scipy
import numpy as np
from edgetpu.detection.engine import DetectionEngine
from imutils.video import VideoStream
from PIL import Image
import argparse
import imutils
import time
import cv2

# Ros
import rospy
from sensor_msgs.msg import CompressedImage
import rospkg
from std_msgs.msg import Int16MultiArray


class FaceDetectorEdgeTPU:

    def __init__(self):
        # Read input parameters
        self.input_image_compressed = rospy.get_param('~input_image_compressed', "usb_cam/image_raw/compressed")
        self.output_image_compressed = rospy.get_param('~output_image', "face_image/compressed")
        self.model_path = rospy.get_param('~model_path', "model.tflite")
        self.threshold = rospy.get_param('~threshold', 0.8)

        # fix path if required
        if "pkg://" in self.model_path:
            rp = rospkg.RosPack()
            path = rp.get_path('braccio_driver')
            self.model_path = self.model_path.replace("pkg://braccio_driver", path)

        # print input parameters
        rospy.loginfo("input_image_compressed: " + self.input_image_compressed)
        rospy.loginfo("output_image_compressed: " + self.output_image_compressed)
        rospy.loginfo("model_path: " + self.model_path)
        rospy.loginfo("threshold: " + str(self.threshold))

        self.model = DetectionEngine(self.model_path)
        self.pub_image = rospy.Publisher(self.output_image_compressed, CompressedImage, queue_size=1)
        self.pub_box = rospy.Publisher("bounding_box", Int16MultiArray, queue_size=1)
        self.subscriber = rospy.Subscriber(self.input_image_compressed,  CompressedImage, self.callback, queue_size=1)

        rospy.spin()

    def callback(self, ros_data):
        if self.pub_box.get_num_connections() == 0 and self.pub_image.get_num_connections() == 0:
            return

        np_arr = np.fromstring(ros_data.data, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        orig = frame.copy()
        frame = Image.fromarray(frame)

        # make predictions on the input frame
        results = self.model.DetectWithImage(frame, threshold=self.threshold, keep_aspect_ratio=True, relative_coord=False)

        # loop over the results
        for r in results:
            # extract the bounding box
            box = r.bounding_box.flatten().astype("int")
            (startX, startY, endX, endY) = box

            # publish bounding box
            box_msg = Int16MultiArray()
            box_msg.data = [r.label_id, startX, startY, endX, endY]
            self.pub_box.publish(box_msg)

            # draw the bounding box and label on the image
            cv2.rectangle(orig, (startX, startY), (endX, endY), (0, 255, 0), 2)

        #### Create CompressedIamge ####
        msg = CompressedImage()
        msg.header.stamp = rospy.Time.now()
        msg.format = "jpeg"
        msg.data = np.array(cv2.imencode('.jpg', orig)[1]).tostring()

        # Publish image with face detections
        self.pub_image.publish(msg)


def main(args):
    rospy.init_node('FaceDetectorEdgeTPU')

    FaceDetectorEdgeTPU()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main(sys.argv)