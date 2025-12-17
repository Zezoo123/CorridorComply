import os 
import cv2
import numpy as np
import imutils
from imutils.contours import sort_contours

DEBUG_DIR = "debug"

def main(file, debug=True):
    """
    This function is used to extract the MRZ from an image
    As a precondition, image should be single page format
    """
    import logging
    logger = logging.getLogger(__name__)
    
    img = cv2.imread(file)
    if img is None:
        if debug:
            logger.error(f"Failed to load image: {file}")
        return None
    H, W = img.shape[:2]
    if debug:
        logger.info(f"Processing image: {W}x{H} pixels")
        cv2.imwrite(f"{DEBUG_DIR}/original.jpg", img)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if debug:
        cv2.imwrite(f"{DEBUG_DIR}/gray.jpg", gray)

    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    if debug:
        cv2.imwrite(f"{DEBUG_DIR}/blurred.jpg", blurred)

    # kernel size based on image width (horizontal)
    rect_w = max(15, int(W * 0.03))
    rect_h = max(5, int(W * 0.01))
    rect_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (rect_w, rect_h))

    # square kernel for connecting lines (vertical)
    #sq_dim = max(15, int(W * 0.02))
    #sqKernel = cv2.getStructuringElement(cv2.MORPH_RECT, (sq_dim, sq_dim))

    blackhat = cv2.morphologyEx(blurred, cv2.MORPH_BLACKHAT, rect_kernel)
    if debug:
        cv2.imwrite(f"{DEBUG_DIR}/blackhat.jpg", blackhat)

    # compute gradient using Scharr filter n)   
    # dx=1, dy=0 detects vertical edges
    grad = cv2.Scharr(blackhat, ddepth=cv2.CV_32F, dx=1, dy=0)
    grad = np.absolute(grad)
    grad = cv2.normalize(grad, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    if debug:
        cv2.imwrite(f"{DEBUG_DIR}/grad.jpg", grad)

    # connect characters horizontally
    # rect_kernel was defined earlier as wide/short (e.g. 25x7)
    # turns "P < A B C" into "█████████"
    grad = cv2.morphologyEx(grad, cv2.MORPH_CLOSE, rect_kernel)
    # threshold to Binary (Black/White)
    thresh = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    # this connects the top MRZ line to the bottom MRZ line
    # thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, sqKernel)
    # ^ removed, catching noise. instead we can grab the bottom two countours
    if debug:
        cv2.imwrite(f"{DEBUG_DIR}/thresh.jpg", thresh)

    cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = imutils.grab_contours(cnts)
    cnts = sort_contours(cnts, method="bottom-to-top")[0] # mrz will always be at the bottom of the passport
    mrz_lines = []
    
    # Debug: log information about contours found
    if debug:
        print(f"Found {len(cnts)} contours")
        print(f"Image dimensions: {W}x{H}")
        print(f"Looking for lines: width > {W * 0.7}px ({0.7*100}%), height > {H * 0.02}px ({0.02*100}%)")
    
    # Track potential candidates for debugging
    candidates = []
    for c in cnts:
        (x, y, w, h) = cv2.boundingRect(c)
        percentWidth = w / float(W)
        percentHeight = h / float(H)
        # Check if in bottom half of image
        in_bottom_half = y > (H / 2)
        
        # mrz line heuristics - wide (over 70% width), in the bottom half of image
        # But also consider lines that are close (60%+) for debugging
        if percentWidth > 0.6 and percentHeight > 0.01:
            candidates.append({
                'x': x, 'y': y, 'w': w, 'h': h,
                'width_pct': percentWidth,
                'height_pct': percentHeight,
                'in_bottom_half': in_bottom_half
            })
        
        if percentWidth > 0.7 and percentHeight > 0.02 and in_bottom_half:
            mrz_lines.append((x, y, w, h))
            if debug:
                print(f"  ✅ MRZ line candidate: {w}x{h} at ({x},{y}) - width: {percentWidth*100:.1f}%")
    
    # If no lines found with strict criteria, try more lenient criteria
    if len(mrz_lines) == 0 and len(candidates) > 0:
        if debug:
            print(f"\n⚠️  No lines found with strict criteria (width > 70%). Found {len(candidates)} potential candidates:")
            # Sort by width percentage descending
            candidates.sort(key=lambda x: x['width_pct'], reverse=True)
            for i, cand in enumerate(candidates[:5]):  # Show top 5
                print(f"  Candidate {i+1}: {cand['w']}x{cand['h']} at ({cand['x']},{cand['y']}) - "
                      f"width: {cand['width_pct']*100:.1f}%, height: {cand['height_pct']*100:.1f}%, "
                      f"bottom half: {cand['in_bottom_half']}")
        
        # Try with more lenient criteria: 60% width, in bottom half
        for cand in candidates:
            if cand['width_pct'] > 0.6 and cand['height_pct'] > 0.015 and cand['in_bottom_half']:
                mrz_lines.append((cand['x'], cand['y'], cand['w'], cand['h']))
                if debug:
                    print(f"  ✅ Using lenient criteria: {cand['w']}x{cand['h']} at ({cand['x']},{cand['y']})")
        
        # If still nothing, try even more lenient: 50% width, any height > 1%
        if len(mrz_lines) == 0:
            for cand in candidates:
                if cand['width_pct'] > 0.5 and cand['height_pct'] > 0.01 and cand['in_bottom_half']:
                    mrz_lines.append((cand['x'], cand['y'], cand['w'], cand['h']))
                    if debug:
                        print(f"  ✅ Using very lenient criteria: {cand['w']}x{cand['h']} at ({cand['x']},{cand['y']})")

    if debug:
        print(f"Found {len(mrz_lines)} MRZ line(s)")
    
    if len(mrz_lines) >= 2:
        line1 = mrz_lines[0]
        line2 = mrz_lines[1]
        min_x = min(line1[0], line2[0])
        min_y = min(line1[1], line2[1])
        max_x = max(line1[0] + line1[2], line2[0] + line2[2])
        max_y = max(line1[1] + line1[3], line2[1] + line2[3])
        mrzBox = (min_x, min_y, max_x - min_x, max_y - min_y)
        if debug:
            print(f"Combined MRZ box: {mrzBox[2]}x{mrzBox[3]} at ({mrzBox[0]},{mrzBox[1]})")
    elif len(mrz_lines) == 1:
        mrzBox = mrz_lines[0]
        if debug:
            print(f"Single MRZ line: {mrzBox[2]}x{mrzBox[3]} at ({mrzBox[0]},{mrzBox[1]})")
    else:
        mrzBox = None
        if debug:
            print("No MRZ lines found matching criteria")

    # Check if MRZ box was found
    if mrzBox is None:
        return None

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
    if debug:
        cv2.imwrite(f"{DEBUG_DIR}/mrz.jpg", mrz)
    return mrz

if __name__ == "__main__":
    file = "../../tests/data/sample_passports/sample.png"
    assert os.path.exists(file), "File does not exist"
    main(file)