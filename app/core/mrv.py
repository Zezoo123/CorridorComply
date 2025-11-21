"""
This module is used to extract the MRZ from an image
As a precondition, image should be single page format
"""
import os 
import cv2
import numpy as np
import imutils
from imutils.contours import sort_contours

debug_dir = "debug"
os.makedirs(debug_dir, exist_ok=True)

file = "../../tests/data/sample_passports/sample.png"
assert os.path.exists(file), "File does not exist"

img = cv2.imread(file)
H, W = img.shape[:2]
cv2.imwrite(f"{debug_dir}/original.jpg", img)

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
cv2.imwrite(f"{debug_dir}/gray.jpg", gray)

blurred = cv2.GaussianBlur(gray, (3, 3), 0)
cv2.imwrite(f"{debug_dir}/blurred.jpg", blurred)

# kernel size based on image width (horizontal)
rect_w = max(15, int(W * 0.03))
rect_h = max(5, int(W * 0.01))
rect_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (rect_w, rect_h))

# square kernel for connecting lines (vertical)
sq_dim = max(15, int(W * 0.02))
sqKernel = cv2.getStructuringElement(cv2.MORPH_RECT, (sq_dim, sq_dim))

blackhat = cv2.morphologyEx(blurred, cv2.MORPH_BLACKHAT, rect_kernel)
cv2.imwrite(f"{debug_dir}/blackhat.jpg", blackhat)

# compute gradient using Scharr filter n)   
# dx=1, dy=0 detects vertical edges
grad = cv2.Scharr(blackhat, ddepth=cv2.CV_32F, dx=1, dy=0)
grad = np.absolute(grad)
grad = cv2.normalize(grad, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
cv2.imwrite(f"{debug_dir}/grad.jpg", grad)

# connect characters horizontally
# rect_kernel was defined earlier as wide/short (e.g. 25x7)
# turns "P < A B C" into "█████████"
grad = cv2.morphologyEx(grad, cv2.MORPH_CLOSE, rect_kernel)
# threshold to Binary (Black/White)
thresh = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
# this connects the top MRZ line to the bottom MRZ line
# thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, sqKernel)
# ^ removed, catching noise. instead we can grab the bottom two countours
cv2.imwrite(f"{debug_dir}/thresh.jpg", thresh)

cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
cnts = imutils.grab_contours(cnts)
cnts = sort_contours(cnts, method="bottom-to-top")[0] # mrz will always be at the bottom of the passport
mrz_lines = []
for c in cnts:
    (x, y, w, h) = cv2.boundingRect(c)
    percentWidth = w / float(W)
    percentHeight = h / float(H)
    # mrz line hueristics - wide (over 70% width), in the botton half of image
    if percentWidth > 0.7 and percentHeight > 0.02:
        mrz_lines.append((x, y, w, h))

if len(mrz_lines) >= 2:
    line1 = mrz_lines[0]
    line2 = mrz_lines[1]
    min_x = min(line1[0], line2[0])
    min_y = min(line1[1], line2[1])
    max_x = max(line1[0] + line1[2], line2[0] + line2[2])
    max_y = max(line1[1] + line1[3], line2[1] + line2[3])
    mrzBox = (min_x, min_y, max_x - min_x, max_y - min_y)
elif len(mrz_lines) == 1:
    mrzBox = mrz_lines[0]
else:
    mrzBox = None

(x, y, w, h) = mrzBox
# add padding to the mrz box
pX = int(w * 0.03)
pY = int(h * 0.04)
# out of bounds check
x = max(0, x - pX)
y = max(0, y - pY)
w = min(W - x, w + (pX * 2))
h = min(H - y, h + (pY * 2))
mrz_roi = gray[y:y+h, x:x+w] # extract from gray image
mrz = cv2.threshold(mrz_roi, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
cv2.imwrite(f"{debug_dir}/mrz.jpg", mrz)