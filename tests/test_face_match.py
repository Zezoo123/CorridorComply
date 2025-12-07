import os
import sys
from pathlib import Path
from PIL import Image

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.face_match import FaceMatchingService

def test_face_matching(document_path: str, selfie_path: str):
    """
    Test face matching between a document image and a selfie.
    
    Args:
        document_path: Path to the document image (e.g., ID card/passport)
        selfie_path: Path to the selfie image
    """
    try:
        # Load images
        print(f"Loading document image: {document_path}")
        document_img = Image.open(document_path)
        
        print(f"Loading selfie image: {selfie_path}")
        selfie_img = Image.open(selfie_path)
        
        # Perform face matching
        print("\nRunning face matching...")
        result = FaceMatchingService.verify_faces(document_img, selfie_img)
        
        # Display results
        print("\n=== Face Matching Results ===")
        print(f"Similarity Score: {result['face_match_score']:.2f}")
        print(f"Match Result: {'✅ MATCH' if result['face_match_result'] else '❌ NO MATCH'}")
        
        if result['error']:
            print(f"\n⚠️  Warning: {result['error']}")
            
        # Interpretation
        print("\n=== Interpretation ===")
        if result['face_match_score'] > 0.7:
            print("High confidence in match")
        elif result['face_match_score'] > 0.5:
            print("Moderate confidence in match")
        else:
            print("Low confidence in match")
            
        return result
        
    except Exception as e:
        print(f"\n❌ Error during face matching: {str(e)}")
        return None

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test face matching between document and selfie images')
    parser.add_argument('document', help='Path to document image (ID/passport)')
    parser.add_argument('selfie', help='Path to selfie image')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.document):
        print(f"Error: Document image not found at {args.document}")
        sys.exit(1)
        
    if not os.path.exists(args.selfie):
        print(f"Error: Selfie image not found at {args.selfie}")
        sys.exit(1)
    
    test_face_matching(args.document, args.selfie)
