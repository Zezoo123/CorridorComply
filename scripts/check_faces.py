# scripts/check_faces.py
import os
import sys
import cv2
import numpy as np
from pathlib import Path
from PIL import Image

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

def check_faces(image_path: str):
    """Check if faces are detected in an image and return face locations."""
    try:
        # Load the image
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img)
        
        # Detect faces using DeepFace
        from deepface import DeepFace
        
        print(f"\nChecking: {image_path}")
        print("=" * 50)
        
        # Try different detectors if needed
        detectors = ['opencv', 'ssd', 'dlib', 'mtcnn', 'retinaface']
        for detector in detectors:
            try:
                print(f"\nTrying {detector} detector...")
                faces = DeepFace.extract_faces(
                    img_path=img_array,
                    detector_backend=detector,
                    enforce_detection=False
                )
                
                if not faces or len(faces) == 0:
                    print(f"❌ No faces found with {detector}")
                else:
                    print(f"✅ Found {len(faces)} face(s) with {detector}:")
                    for i, face in enumerate(faces, 1):
                        area = face.get('facial_area', {})
                        print(f"  Face {i}:")
                        print(f"    Position: (x:{area.get('x', 'N/A')}, y:{area.get('y', 'N/A')})")
                        print(f"    Size: {area.get('w', 'N/A')}x{area.get('h', 'N/A')}")
                        print(f"    Confidence: {face.get('confidence', 'N/A')}")
                    
            except Exception as e:
                print(f"⚠️  Error with {detector}: {str(e)}")
                continue
                
        return True
        
    except Exception as e:
        print(f"\n❌ Error processing image: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_faces.py <image_path>")
        sys.exit(1)
        
    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(f"Error: Image not found at {image_path}")
        sys.exit(1)
    
    check_faces(image_path)