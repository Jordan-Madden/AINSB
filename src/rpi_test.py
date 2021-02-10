'''
    Author: Jordan Madden
    Usage: python rpi_test.py --model="v1" 
'''

import tflite_runtime.interpreter as tflite
import pyrealsense2.pyrealsense2 as rs
from imutils.video import FPS
from threading import Thread
import importlib.util
import numpy as np
import argparse
import time
import cv2
import os
import sys

# Construct and parse the command line arguments 
ap = argparse.ArgumentParser()
ap.add_argument('--model', help='Provide the path to the TFLite file, default is models/detect.tflite',
                    default='v1')
ap.add_argument('--threshold', help='Minimum confidence threshold for displaying detected objects',
                    default=0.5)
ap.add_argument('--resolution', help='Desired webcam resolution in WxH. If the webcam does not support the resolution entered, errors may occur.',
                    default='640x480')               
args = vars(ap.parse_args())

class RealSenseVideo:
    def __init__(self, width=640, height=480):
        # Frame dimensions of camera
        self.width = width
        self.height = height

        # Build and enable the depth and color frames
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        self.config.enable_stream(rs.stream.depth, self.width, self.height, rs.format.z16, 30)
        self.config.enable_stream(rs.stream.color, self.width, self.height, rs.format.bgr8, 30)

        # Start streaming
        self.pipeline.start(self.config)
        
        # Read the first frame from the stream
        self.frame = self.pipeline.wait_for_frames()
        self.depth_frame = self.frame.get_depth_frame()
        self.color_frame = self.frame.get_color_frame()

        # Variable to check if thread should be stopped
        self.stopped = False

    def start(self):
        # Start the thread to read the frames from the video stream
        Thread(target=self.update, args=()).start()
        return self

    def update(self):
        while True:
            # Stop streaming in indicator is set
            if self.stopped:
                return

            # Otherwise read the next frame in the stream
            self.frame = self.pipeline.wait_for_frames()
            self.depth_frame = self.frame.get_depth_frame()
            self.color_frame = self.frame.get_color_frame()
            if not self.depth_frame or not self.color_frame:
                return

    def read(self):
        # Return the most recent color and depth frame
        return self.color_frame, self.depth_frame

    def stop(self)        :
        # Stop the video stream
        self.stopped = True
        self.pipeline.stop()

def detect(input_data, input_details, output_details):
    # Perform the object detection and get the results
    interpreter.set_tensor(input_details[0]['index'],input_data)
    interpreter.invoke()
    
    boxes = interpreter.get_tensor(output_details[0]['index'])[0] 
    classes = interpreter.get_tensor(output_details[1]['index'])[0] 
    scores = interpreter.get_tensor(output_details[2]['index'])[0]

    return (boxes, classes, scores)

def visualize_boxes(frame, boxes, scores, classes, H, W):
    # Get the bounding box coordinates
    coordinates = get_bb_coordinates(boxes, scores, H, W)
    i = 0
    
    for coordinate in coordinates:
        # Get the bounding box coordinates
        x1, y1, x2, y2 = coordinate

        # Draw bounding box
        cv2.rectangle(frame, (x1,y1), (x2,y2), (0,255,0), 2)

def filter_distance(depth_frame, x, y):
    #List to store the consecutive distance values and randomly initialized variable
    distances = []
    positive = np.random.randint(low=30, high=100)

    i = 0
    while(i < 75):
        # Extract the depth value from the camera
        dist = int(depth_frame.get_distance(x, y)*100)
        
        # Store the last positive value for use in the event that the
        # value returned is 0
        if dist != 0:
            positive = dist
        elif dist == 0:
            positive == positive

        # Add the distances to the list
        distances.append(positive)
        i += 1

    # Convert the list to a numpy array and return it
    distances = np.asarray(distances)
    return int(distances.mean())

def get_bb_coordinates(detections, scores, H, W, confidence=0.5):
    # Initialize list to store bounding box coordinates of each bounding box
    coordinates = []

    for detection, score in zip(detections, scores):
        # Only move forward if score is above the threshold
        if score > confidence:
            # Extract the coordinates of the detections and normalize each detection
            y1, x1, y2, x2 = detection
            y1 = int(H*y1)
            x1 = int(W*x1)
            y2 = int(H*y2)
            x2 = int(W*x2)

            # Add the coordinates to the coordinate list
            coordinates.append([x1, y1, x2, y2])

    return coordinates

def command(val, frame):
    # Display command on the screen
    text = "Command: {}".format(val)
    cv2.rectangle(frame, (0, 0), (180, 25), (255, 255, 255), -1)
    cv2.putText(frame, text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX,
            0.5, (0, 0, 0), thickness=2)

def checkpoints(depth_frame):
    global checkpoint_detection
    checkpoint_detection = False
    W, H = 640, 480

    # Coordinates of the points to be checked in the frame
    center = filter_distance(depth_frame, W//2, H//2)
    right = filter_distance(depth_frame, W//2 + 90, H//2)
    left = filter_distance(depth_frame, W//2 - 90, H//2)
    l_center = filter_distance(depth_frame, W//2, H//2 + 180)
    l_right = filter_distance(depth_frame, W//2 + 60, H//2 + 180)
    l_left = filter_distance(depth_frame, W//2 - 60, H//2 + 180)
    
    # If any of the checkpoints are triggered raise a notification
    if ((center < min_distance) or (left < min_distance) or (right < min_distance) or 
        (l_center < min_distance) or (l_left < min_distance) or (l_right < min_distance)):
        checkpoint_detection = True
        return True
    
    return False

def stop_moving(dist, depth_frame):
    # Stop moving if an object is detected within 1.5 meters or if any of the 
    # chekpoints are triggered
    if (checkpoints(depth_frame)  or (dist < min_distance)):
        return True    
    
    # If none of the conditions are met, keep moving
    return False

def navigate(frame, depth_frame, dist, left, right):
    # Determine the midpoint of each detection and the distance between the object and 
    # the left and right borders of the frame
    midX = (left+right)//2
    dist_left = left - 0
    dist_right = 640 - right
    
    if stop_moving(dist, depth_frame):
        # Stop moving for a bit while deciding what action to take
        command("Stop", frame)
        time.sleep(0.5)

        if dist_left > dist_right:
            command("Left", frame)
        elif dist_right > dist_left:
            command("Right", frame)
    else:
        # Move forward
        command("Forward", frame)

if __name__ == "__main__":
    # Declare relevant constants
    if args["model"] == "v1":
        model_path = '/home/pi/tflite/detect.tflite'
    if args["model"] == "v2":
        model_path = '/home/pi/tflite/model.tflite'
        
    PATH_TO_MODEL_DIR = model_path
    MIN_CONF_THRESH = args["threshold"]

    # Get the desired image dimensions
    resW, resH = args["resolution"].split('x')
    imW, imH = int(resW), int(resH)

    # Declare variables and constants for navigation
    checkpoint_detection = False
    min_distance = 120

    # Load TF Lite model
    print('[INFO] loading model...')
    start_time = time.time()

    interpreter = tflite.Interpreter(model_path=PATH_TO_MODEL_DIR)
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    print('Done! Took {} seconds'.format(elapsed_time))

    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    height = input_details[0]['shape'][1]
    width = input_details[0]['shape'][2]

    floating_model = (input_details[0]['dtype'] == np.float32)

    input_mean = 127.5
    input_std = 127.5

    # Initialize video stream and the FPS counter
    print('[INFO] running inference for realsense camera...')
    video = RealSenseVideo(width=imW, height=imH).start()
    fps = FPS().start()
    time.sleep(1)

    while True:
        # Get the video frames from the camera
        color_frame, depth_frame = video.read()
        
        # Convert images to numpy arrays and get the frame dimensions
        depth_image = np.asanyarray(depth_frame.get_data())
        frame1 = np.asanyarray(color_frame.get_data())

        # Acquire frame and resize to expected shape [1xHxWx3]
        frame = frame1.copy()
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_resized = cv2.resize(frame_rgb, (width, height))
        input_data = np.expand_dims(frame_resized, axis=0)

        # Normalize pixel values if using a floating model(non-quantized model)
        if floating_model:
            input_data = (np.float32(input_data) - input_mean) / input_std
        
        # Run the object detection and get the results
        boxes, classes, scores = detect(input_data, input_details, output_details)
         
        # Visualize the detections
        visualize_boxes(frame, boxes, scores, classes, imH, imW)
        
        points = get_bb_coordinates(boxes, scores, imH, imW)
        for point in points:
            # Extract the bounding box coordinates 
            startX, startY, endX, endY = point
            
            # Find the midpoint coordinates
            midX = (startX+endX)//2
            midY = startY+endY)//2
            
            # Find the distance at each point
            dist = filter_distance(depth_frame, midX, midY)
            
            # Draw a circle at the midpoint for visual validation
            cv2.circle(frame, (midX, midY), radius=5, 
                color=(0,0,255), thickness=2)
            
            # Display the distance of each object from the camera
            text = "Distance: {}cm".format(dist)
            cv2.putText(frame, text, (startX, startY+20), cv2.FONT_HERSHEY_SIMPLEX, 
                0.6, (0, 0, 255), thickness=2)

            # Determine what command to give to the user
            navigate(frame, depth_frame, dist, startX, endX)

        if not checkpoint_detection:
            if checkpoints(depth_frame):
                command("Stop", frame)
            else:
                command("Forward", frame)

        checkpoint_detection = False
                
        # All the results have been drawn on the frame, so it's time to display it.
        cv2.imshow('Object Detector', frame)

        # Update FPS counter
        fps.update()

        # Press 'q' to quit
        if cv2.waitKey(1) == ord('q'):
            fps.stop()
            break

    # Show the elapsed time and the respective fps
    print("[INFO] elapsed time: {:.2f}".format(fps.elapsed()))
    print("[INFO] approximate fps: {:.2f}".format(fps.fps()))
        
    # Stop the video stream
    cv2.destroyAllWindows()
    video.stop()
