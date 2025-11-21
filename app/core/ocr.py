import os 
import cv2

debug_dir = "debug"
os.makedirs(debug_dir, exist_ok=True)

file_example = "../../tests/data/sample_passports/2.png"
img = cv2.imread(file_example)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
blurred = cv2.GaussianBlur(gray, (3, 3), 0)
rect_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 7))
blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, rect_kernel)


cv2.imwrite(f"{debug_dir}/original.jpg", img)
cv2.imwrite(f"{debug_dir}/gray.jpg", gray)
cv2.imwrite(f"{debug_dir}/blurred.jpg", blurred)
cv2.imwrite(f"{debug_dir}/blackhat.jpg", blackhat)