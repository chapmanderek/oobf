# main.py
import cv2
import io
import numpy as np
import os
import picar_4wd as fc

import sys
import time
import picamera
import picamera.array

from datetime import date
from PIL import Image

from process_images import Process_Image
# from picar_4wd.pwm import PWM
# from picar_4wd.pin import Pin

class car_scanner:
    def __init__(self):
        self.arc_to_scan = 25 #scans both sides so 15 would be a total of 30 degrees
        self.buffer_distance = 30 #mm
        self.scan_step = 5
        self.debug = False
        self.camera_flipped = False

        self.time_forward = None
        self.power = 10

        self.max_dist_from_shelf = 20 #mm
        self.min_dist_from_shelf = 15 #mm

    def begin_scan(self):
        pass

    def check_environment(self):
        dists_in_front = []
        forward = "clear"
        drift = "no"
			
        #scan a small section in front of car
        for angle in [self.arc_to_scan, 0, -self.arc_to_scan]:
            d = fc.get_distance_at(angle)
            if d < 0 : dists_in_front.append(100)
            else : dists_in_front.append(d)

            time.sleep(0.4)
        dists_in_front = np.array(dists_in_front)

        if self.debug : print(dists_in_front)

        #check if somethings in front thats too close
        if any(dists_in_front <= self.buffer_distance):
            forward = 'blocked'
        
        #check distance to book shelf
        dist_to_shelf = fc.get_distance_at(-90)
        if dist_to_shelf < self.min_dist_from_shelf:
            drift = 'left'
        elif dist_to_shelf > self.max_dist_from_shelf:
            drift = "right"

        return {'forward':forward, 'drift':drift, 'dist2shelf':dist_to_shelf}
    
    def move_forward(self, drift):
        if drift == 'no': 
            fc.forward(self.power)
        elif drift == "left":
            fc.drift_left(self.power)
        elif drift == "right":
            fc.drift_right(self.power)

        time.sleep(self.time_forward)

        fc.stop()

    def stop(self):
        fc.stop()

def take_single_picture(camera, stream, flipped):
    # camera.capture(stream, 'jpeg')
    # stream.seek(0)
    # image = Image.open(stream)
    
    time.sleep(.1)
    camera.capture(stream, format='bgr')
    stream.seek(0)
    image = stream.array
    
    if flipped:
        image = cv2.rotate(image, cv2.ROTATE_180)
    return image

def stich_images_together(images):
    """assumes a list of cv2 images"""
    stitcher = cv2.Stitcher_create()
    (status, stitched_img) = stitcher.stitch(images)

    return (status, stitched_img)

def call_numbers2dict_results(call_numbers):
        #determine direction ascending or descending of first two books
        if call_numbers[0] > call_numbers[1] : descending = True
        else : descending = False

        results = []
        #add in first book
        results.append({'book_number' : 1, 'call_number' : call_numbers[0], 'out_of_order' : False})

        #loop through the remaining books and check each book is in order according to the flag
        for idx in range(1, len(call_numbers)):
            #create a list of dictionaries
            if descending:
                if call_numbers[idx-1] > call_numbers[idx]:
                    results.append({'book_number' : idx+1, 'call_number' : call_numbers[idx], 'out_of_order' : False})
                else:
                    results.append({'book_number' : idx+1, 'call_number' : call_numbers[idx], 'out_of_order' : True})
            else:
                if call_numbers[idx-1] < call_numbers[idx]:
                    results.append({'book_number' : idx+1, 'call_number' : call_numbers[idx], 'out_of_order' : False})
                else:
                    results.append({'book_number' : idx+1, 'call_number' : call_numbers[idx], 'out_of_order' : True})
        return results

def process_results(call_numbers, shelf_number = 1):
    """process entire shelf list of call numbers for out of order books"""
    #?what if theres only two call numbers?#

    #go through the results and turn it into one flat list
    flat_call = []
    for each in call_numbers:
        flat_call.extend(each)
    call_numbers = flat_call[:]

    #remove Nones
    call_numbers = [x for x in call_numbers if x]

    #find and remove duplicate neighbor entries
    idx_keep = [0]
    for i in range(1, len(call_numbers)):
        if call_numbers[i-1] != call_numbers[i]:
            idx_keep.append(i)
    # idx_keep.append(len(call_numbers)-1)
    
    temp_call = [call_numbers[i] for i in idx_keep]
    call_numbers = temp_call[:]
    
    #find OOOB and create list of dicts to send to aws
    results = call_numbers2dict_results(call_numbers)
    
    return results

def send_results_to_aws(results, aws, images = None):
    pass

#setup objects and lists to retain information
cs = car_scanner()
cs.debug = False
cs.camera_flipped = True
cs.time_forward = 0.25


# camera_stream = io.BytesIO()
results = []
images = []

#create directory for images
today = date.today()
ymd = today.strftime("%Y-%m-%d")  # YYYY-MM-DD

current_directory = os.getcwd()
new_directory = 'images_' + ymd + '/'
images_path = os.path.join(current_directory, new_directory)

if not os.path.exists(images_path):
    os.makedirs(images_path)
    print('created new directory at: \n', images_path)

with picamera.PiCamera() as camera:
    camera.resolution = (1024, 768)
    camera.start_preview()

    # Camera warm-up time
    print('warming camera up')
    time.sleep(2)
    with picamera.array.PiRGBArray(camera) as stream:
        for i in range(3):
            # print(f'on loop #{i}')
            processor = Process_Image()

            #take picture and write to the images directory
            time.sleep(0.25) #make sure we're not moving
            img = take_single_picture(camera, stream, cs.camera_flipped)
            img_name = os.path.join(images_path, f'image_{len(images)}.jpg')
            cv2.imwrite(img_name, img)
            print(f'writing image: images{i}.jpg')

            #keep both the image and the results from processing the label
            images.append(img)
            output = processor.process(img)
            if output and output[0] == 'error' : print(output)
            else:
                print(output) 
                results.append(output)

            #check the cars environment and then move forward with some drift if nessecary
            local_environment = cs.check_environment()
            # if local_environment['forward'] != 'blocked':
            print('moving --------------------\n')
            cs.move_forward(local_environment['drift'])

#process all of the call numbers into a list of dictionaries for QAWS
if len(results) > 1:
    print('results object: ', results)
    call_numbers_dict = process_results(results)
    send_results_to_aws(call_numbers_dict, 'aws-key-info')
    
    print('final output: ')
    for each in call_numbers_dict:
        print(each)

else:
    print('no call numbers found')

cs.stop()
