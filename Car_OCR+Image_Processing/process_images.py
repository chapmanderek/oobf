import enum
from typing import List
import cv2
import numpy as np
import math
import warnings
import sys

import pytesseract

class Process_Image():
    def __init__(self) -> List:
        self.call_numbers = []
        self.num_lines_found = 0
        self.lines_kept = 0

        self.slices = []
        self.labels = []
        self.im_white = []
        self.ocr_results = []
        self.results = []

    def __repr__(self) -> str:
        rep = ""
        rep += 'Process_Image()\n'
        
        for each in self.results:
            rep += repr(each) + '\n'
        return rep

    def process(self, image):
        """Assumes asingle image that is in BGR format."""
        image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        #edge and line detection
        sobelx = self.get_sobelx(image_bgr)
        lines = self.detect_lines(sobelx)
        if not lines:
            return ("error", "no lines found.")
        self.num_lines_found = len(lines)

        img_height = image_bgr.shape[0]
        extended_lines = self.extend_lines(lines, img_height)
        extended_lines = self.remove_duplicate_lines(extended_lines, 50)
        self.lines_kept = len(lines)

        if self.lines_kept < 2:
            return ("error", "didnt find enough lines between books")

        #slice up image into (hopefully) individual books
        self.slices = self.slice_image(extended_lines, image_bgr)

        if len(self.slices) == 0:
            return ("error", "didnt find any books")

        #extract labels from slices and get call numbers
        for i, s in enumerate(self.slices):
            label, im_white, white_values = self.extract_label(s)
            self.im_white.append(im_white)
            self.labels.append(label)

            if type(label) is np.ndarray:
                ocr_result = self.label2string(s)   #### !! was label
                self.ocr_results.append(ocr_result)

                # print(ocr_result)
            if ocr_result:
                call_number = self.string2call_number(ocr_result)
                self.call_numbers.append(call_number)

        print('writing diagnostic imagery')
        self.output_diagnostic_images(extended_lines, image)

        #remove None's from call_numbers
        self.call_numbers = [x for x in self.call_numbers if x]

        return self.call_numbers

    def get_sobelx(self, img):
        im_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        im_gray = cv2.GaussianBlur(im_gray, (3,3), 0)

        sobelx = cv2.Sobel(src=im_gray, ddepth=cv2.CV_8UC1, dx=1, dy=0)
        sobely = cv2.Sobel(src=im_gray, ddepth=cv2.CV_8UC1, dx=0, dy=1)
        
        return sobelx

    def remove_duplicate_lines(self, lines, threshold):
        output_lines = []
        used_x = np.array((0))
        for line in lines:
            cur_x1 = line[0]
            
            smallest_diff = np.min(np.abs(used_x - cur_x1))
            
            if smallest_diff > threshold:
                output_lines.append(line)
                used_x = np.append(used_x, cur_x1)

        return(output_lines)
    
    def extend_lines(self, lines, height):
        ext_lines = []
        for line in lines:
            ext_lines.append(self.extend_line(line, height))
            
        return ext_lines

    def extend_line(self, line, img_height):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            x3, y3 = self.extend_line_to_bottom2(line, img_height)
            x0, y0 = self.extend_line_to_top2(line)

        return [x0, y0, x3, y3]

    def extend_line_to_bottom2(self, line, height):
        [x1, y1, x2, y2] = line
        slope = (y2-y1) / (x2-x1)

        if slope > 0:
            x3, y3 = x2, y2
            while(y3 < height):
                x3 = x3 + 1
                y3 = y3 + slope
        
        if slope < 0:
            x3, y3 = x2, y2
            while(y3 < height):
                x3 = x3 - 1
                y3 = y3 - slope

        return (x3, height)

    def extend_line_to_top2(self, line):
        [x1, y1, x2, y2] = line
        slope = (y2-y1) / (x2-x1)

        lenAB = math.sqrt(math.pow(x1 - x2, 2.0) + math.pow(y1 - y2, 2.0))

        if slope > 0:
            x0, y0 = x1, y1
            while(y0 > 0):
                x0 = x0 - 1
                y0 = y0 - slope
        
        if slope < 0:
            x0, y0 = x1, y1
            while(y0 > 0):
                x0 = x0 + 1
                y0 = y0 + slope

        y0 = 0
        return(x0, y0)    
        
    def detect_lines(self, sobelx):
        deg = 0.75
        lines = cv2.HoughLinesP(sobelx, 1, (deg/180 * 3.14159), 100, minLineLength= 500, maxLineGap=5)
        if lines is not None:
            lines = [list(l[0])for l in lines]
        
        return lines

    def slice_image(self, lines, img):
        lines = sorted(lines, key=lambda x: x[0])
        slices = []
        
        for i in range(1, len(lines)):
            x1, y1, x2, y2 = lines[i]
            x3, y3, x4, y4 = lines[i-1]

            pts =[[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
            pts = np.array(pts)
            rect = cv2.boundingRect(pts)
            x,y,w,h = rect
            
            t_cropped = img[y:y+h, x:x+w].copy()
            slices.append(t_cropped)

        return(slices)
    
    def extract_label(self, im_slice, min_white_threshold = 200, label_threshold = 180):
        height, width, _ = im_slice.shape
        im_slice = im_slice[300:, :]
        im_hsl = cv2.cvtColor(im_slice, cv2.COLOR_BGR2HLS)
        im_white = cv2.inRange(im_hsl,  np.array([0,min_white_threshold,0]), 
                                        np.array([255,255,255]))
        
        kernel_height = 20
        kernel_step   = 10
        kernel_top    = 0
        white_values  = []
        
        while(kernel_top < im_white.shape[0]):
            avg_white = np.mean(im_white[kernel_top:kernel_top+kernel_height, :])
            white_values.append(avg_white)
            kernel_top += kernel_step
        
        # calculate the top 5% of whiteness in the picture
        n = int(len(white_values) * 0.95)
        label_threshold = int(sorted(white_values)[n])
        n = int(len(white_values) * 0.80)
        bottom_threshold = int(sorted(white_values)[n])
        
        top_at    = None
        bottom_at = None
        found_top = False
        for i in range(len(white_values)):
            if white_values[i] > label_threshold:
                if not top_at: 
                    top_at = (i * kernel_step) #+ kernel_height
            if top_at and white_values[i] <= bottom_threshold:
                bottom_at = (i * kernel_step) + kernel_height

        cropped = im_slice[top_at:bottom_at, :].copy()

        return [cropped, im_white, white_values]

    def output_diagnostic_images(self, lines, image):
        self.visualize_found_lines(lines, image)

        for i, slice in enumerate(self.slices):
            cv2.imwrite(f'current_run/slice{i}.jpg', self.slices[i])
            cv2.imwrite(f'current_run/label{i}.jpg', self.labels[i])
            cv2.imwrite(f'current_run/white{i}.jpg', self.im_white[i])

    def visualize_found_lines(self, lines, img):
        for i in range(len(lines)):
            [x1, y1, x2, y2] = lines[i]
            cv2.line(img, (x1, y1), (x2, y2), (255, 0, 255), 3)
        _ = cv2.imwrite(f'current_run/lines.jpg', img)


    def label2string(self, label):
        config = '--oem 3 --psm 6'
        ocr_result = pytesseract.image_to_string(label, config = config, lang='eng')
        return ocr_result
    
    def string2call_number(self, ocr_result):
        if ocr_result:
            ocr_result = ocr_result.strip()
            split_results = ocr_result.split('\n')

            if len(split_results) < 2:
                return None

            split_results = [''.join(filter(str.isalnum, e)) for e in split_results]

            for i in range(len(split_results)-1):
                if split_results[i].replace('.',"").isnumeric() and split_results[i+1].isalpha():
                    call_number = (split_results[i], split_results[i+1])
                    if len(call_number[0]) > 3:
                        cnum = call_number[0][0:3] + '.' + call_number[0][3:]
                        call_number = (cnum, call_number[1])
                        
                    return(call_number)
        else : return None


if __name__ == '__main__':
    img_path = sys.argv[1]
    img = cv2.imread(img_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    processer = Process_Image()
    processer.process(img)
    print(processer)