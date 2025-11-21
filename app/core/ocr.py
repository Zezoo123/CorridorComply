import os 
import cv2
import numpy as np
import imutils
from imutils.contours import sort_contours

debug_dir = "debug"
os.makedirs(debug_dir, exist_ok=True)

file_example = "../../tests/data/sample_passports/2.png"
img = cv2.imread(file_example)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
blurred = cv2.GaussianBlur(gray, (3, 3), 0)

rect_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 7))
sqKernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))

blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, rect_kernel)

# Take gradient of img using Sobel operator
grad = cv2.Sobel(blackhat, ddepth=cv2.CV_32F, dx=1, dy=0, ksize=-1)
grad = np.absolute(grad)
(minVal, maxVal) = (np.min(grad), np.max(grad))
grad = (grad - minVal) / (maxVal - minVal)
grad = (grad * 255).astype("uint8")

#cv2.imwrite(f"{debug_dir}/grad.jpg", grad)


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
cnts = sort_contours(cnts, method="bottom-to-top")[0]
# initialize the bounding box associated with the MRZ
mrzBox = None


#cv2.imwrite(f"{debug_dir}/original.jpg", img)
#cv2.imwrite(f"{debug_dir}/gray.jpg", gray)
#cv2.imwrite(f"{debug_dir}/blurred.jpg", blurred)
#cv2.imwrite(f"{debug_dir}/blackhat.jpg", blackhat)