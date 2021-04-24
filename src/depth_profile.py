'''
    Author: Jordan Madden
    Usage: python depth_profile.py
'''

import matplotlib.pyplot as plt
from realsense import RealSense
from imutils.video import FPS
import numpy as np
import time
import cv2

def filter_distance(depth_frame, x, y):
    #List to store the consecutive distance values and randomly initialized variable
    distances = []
    positive = np.random.randint(low=30, high=100)

    i = 0
    while(i < 50):
        # Extract the depth value from the camera
        dist = int(depth_frame.get_distance(x, y) * 100)
        
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

if __name__ == "__main__":
    video = RealSense(width=640, height=480).start()
    fps = FPS().start()
    
    while True:
        color_frame, depth_frame = video.read()
        
        # Convert images to numpy arrays and get the frame dimensions
        depth_image = np.asanyarray(depth_frame.get_data())
        frame = np.asanyarray(color_frame.get_data())
        
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Draw line on screen to visulalize 300px
        cv2.line(frame, (100, 240), (600, 240), (0, 160, 200), 2)
        #depth = depth_image[100:500,240:240].astype(float)*depth_scale
        pts = []
        
        for i in range(500):
            pts.append(filter_distance(depth_frame, 100+i, 240))
        
        print(pts)
        plt.plot(pts)
        plt.show()
        
        # All the results have been drawn on the frame, so it's time to display it.
        cv2.imshow('Object Detector', frame)
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
        
        
        
        
        
        
