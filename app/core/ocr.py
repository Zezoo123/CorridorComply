"""
This module is used to extract the MRZ from a passport image
As a pre requisites, passport image should be single page format
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
print(len(mrz_lines))
exit()
# 4. REMOVE EROSION
# thresh = cv2.erode(thresh, None, iterations=2)  <-- DELETE THIS

# Optional: Small dilation to ensure solidity (instead of erosion)
# thresh = cv2.dilate(thresh, None, iterations=2)


# apply a closing operation using the rectangular kernel to close
# gaps in between letters -- then apply Otsu's thresholding method
grad = cv2.morphologyEx(grad, cv2.MORPH_CLOSE, rect_kernel)
thresh = cv2.threshold(grad, 0, 255,
	cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
# perform another closing operation, this time using the square
# kernel to close gaps between lines of the MRZ, then perform a
# series of erosions to break apart connected components
thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, sqKernel)
thresh = cv2.erode(thresh, None, iterations=2)

#cv2.imwrite(f"{debug_dir}/thresh.jpg", thresh)

# find contours in the thresholded image and sort them from bottom
# to top (since the MRZ will always be at the bottom of the passport)
cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
	cv2.CHAIN_APPROX_SIMPLE)
cnts = imutils.grab_contours(cnts)
cnts = sort_contours(cnts, method="bottom-to-top")[0] # mrz will always be at the bottom of the passport
# initialize the bounding box associated with the MRZ
mrzBox = None
#print(cnts)


# loop over the contours
for c in cnts:
	# compute the bounding box of the contour and then derive the
	# how much of the image the bounding box occupies in terms of
	# both width and height
	(x, y, w, h) = cv2.boundingRect(c)
	percentWidth = w / float(W)
	percentHeight = h / float(H)
	print(percentWidth, percentHeight)
	# if the bounding box occupies > 80% width and > 4% height of the
	# image, then assume we have found the MRZ
	if percentWidth > 0.7 and percentHeight > 0.02:
		mrzBox = (x, y, w, h)
		break

# if the MRZ was not found, exit the script
if mrzBox is None:
	print("[INFO] MRZ could not be found")
	exit(0)
# pad the bounding box since we applied erosions and now need to
# re-grow it
(x, y, w, h) = mrzBox
pX = int((x + w) * 0.03)
pY = int((y + h) * 0.03)
(x, y) = (x - pX, y - pY)
(w, h) = (w + (pX * 2), h + (pY * 2))
# extract the padded MRZ from the image
mrz = img[y:y + h, x:x + w]
cv2.imwrite(f"{debug_dir}/mrz.jpg", mrz)
#cv2.imwrite(f"{debug_dir}/original.jpg", img)
#cv2.imwrite(f"{debug_dir}/glurred.jpg", blurred)
#cv2.imwrite(f"{debug_dir}/blackhat.jpg", blackhat)ray.jpg", gray)
#cv2.imwrite(f"{debug_dir}/b