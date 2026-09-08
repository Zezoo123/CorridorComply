#!/usr/bin/env python3
"""
Debug script for OCR process - tests each step individually.

This script helps debug OCR issues by:
1. Testing MRZ extraction step by step
2. Showing intermediate images (if debug=True)
3. Testing OCR text extraction
4. Testing MRZ parsing
"""
import sys
import os
import tempfile
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import easyocr

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.mrz_detect import main as mrz_main
from app.core.ocr import parse_mrz, extract_mrz_from_image, validate_document_ocr

def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def test_mrz_extraction(image_path: str, debug: bool = True):
    """Test MRZ extraction from image file (tries all orientations)"""
    print_section(f"Step 1: MRZ Extraction from {image_path}")
    
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return None
    
    print(f"📄 Loading image: {image_path}")
    img = cv2.imread(image_path)
    if img is None:
        print(f"❌ Failed to load image with OpenCV")
        return None
    
    H, W = img.shape[:2]
    print(f"✅ Image loaded: {W}x{H} pixels")
    
    # Create debug directory
    if debug:
        debug_dir = Path("debug")
        debug_dir.mkdir(exist_ok=True)
        print(f"📁 Debug images will be saved to: {debug_dir.absolute()}")
    
    # Try different orientations
    orientations = [0, 90, 180, 270]
    print(f"\n🔄 Trying MRZ extraction at different orientations (0°, 90°, 180°, 270°)...")
    
    for orientation in orientations:
        try:
            if orientation == 0:
                img_rotated = img
            elif orientation == 90:
                img_rotated = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
            elif orientation == 180:
                img_rotated = cv2.rotate(img, cv2.ROTATE_180)
            elif orientation == 270:
                img_rotated = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            
            # Save rotated image temporarily
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                tmp_path = tmp_file.name
                cv2.imwrite(tmp_path, img_rotated)
            
            try:
                mrz_image = mrz_main(tmp_path, debug=debug and orientation == 0)  # Only debug first orientation
                
                if mrz_image is not None:
                    print(f"✅ MRZ found at {orientation}° orientation!")
                    print(f"   MRZ region: {mrz_image.shape[1]}x{mrz_image.shape[0]} pixels")
                    if debug:
                        print(f"   Saved to: debug/mrz.jpg")
                    return mrz_image
                else:
                    print(f"   ❌ No MRZ at {orientation}°")
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    
        except Exception as e:
            print(f"   ⚠️  Error at {orientation}°: {str(e)}")
            continue
    
    print("\n❌ MRZ extraction failed at all orientations")
    print("\n💡 Possible reasons:")
    print("   - Image doesn't contain a passport/ID with MRZ")
    print("   - MRZ is not clearly visible")
    print("   - Image quality is too poor")
    print("   - MRZ lines don't meet detection criteria")
    return None

def test_mrz_extraction_from_pil(image_path: str):
    """Test MRZ extraction from PIL Image (as used in the service)"""
    print_section(f"Step 1b: MRZ Extraction from PIL Image (Service Method)")
    
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return None
    
    try:
        print(f"📄 Loading image with PIL: {image_path}")
        pil_image = Image.open(image_path)
        print(f"✅ PIL Image loaded: {pil_image.size[0]}x{pil_image.size[1]} {pil_image.mode}")
        
        print("\n🔄 Running extract_mrz_from_image()...")
        mrz_image = extract_mrz_from_image(pil_image)
        
        if mrz_image is None:
            print("❌ MRZ extraction returned None")
            return None
        
        print(f"✅ MRZ region extracted: {mrz_image.shape[1]}x{mrz_image.shape[0]} pixels")
        return mrz_image
        
    except Exception as e:
        print(f"❌ Error during MRZ extraction: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_ocr_text_extraction(mrz_image: np.ndarray):
    """Test OCR text extraction from MRZ image"""
    print_section("Step 2: OCR Text Extraction")
    
    if mrz_image is None:
        print("❌ No MRZ image provided")
        return None
    
    try:
        print("🔄 Initializing EasyOCR reader...")
        print("   (This may take a while on first run)")
        reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        print("✅ EasyOCR reader initialized")
        
        print("\n🔄 Extracting text from MRZ image...")
        results = reader.readtext(mrz_image, detail=0)
        
        if not results:
            print("❌ No text extracted from MRZ image")
            print("\n💡 Possible reasons:")
            print("   - MRZ region is too small or unclear")
            print("   - Text is not in English")
            print("   - Image quality is too poor")
            return None
        
        mrz_text = "\n".join(results)
        mrz_text_cleaned = mrz_text.upper().replace(" ", "").strip()
        
        print(f"✅ Text extracted ({len(results)} lines)")
        print(f"\n📝 Raw OCR text:")
        print("-" * 70)
        print(mrz_text)
        print("-" * 70)
        print(f"\n📝 Cleaned MRZ text:")
        print("-" * 70)
        print(mrz_text_cleaned)
        print("-" * 70)
        
        return mrz_text_cleaned
        
    except Exception as e:
        print(f"❌ Error during OCR text extraction: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_mrz_parsing(mrz_text: str):
    """Test MRZ parsing"""
    print_section("Step 3: MRZ Parsing")
    
    if not mrz_text:
        print("❌ No MRZ text provided")
        return None
    
    try:
        print("🔄 Parsing MRZ text...")
        mrz_data = parse_mrz(mrz_text)
        
        if "error" in mrz_data:
            print(f"❌ MRZ parsing failed: {mrz_data['error']}")
            print("\n💡 Possible reasons:")
            print("   - MRZ text format is incorrect")
            print("   - OCR misread some characters")
            print("   - Text is not a valid TD3 MRZ format")
            return mrz_data
        
        print("✅ MRZ parsed successfully!")
        print("\n📋 Parsed MRZ Data:")
        print("-" * 70)
        for key, value in mrz_data.items():
            if key != "error":
                print(f"  {key}: {value}")
        print("-" * 70)
        
        if mrz_data.get("valid_composite", False):
            print("\n✅ MRZ checksums validated!")
        else:
            print("\n⚠️  MRZ checksums failed (but data was parsed)")
        
        return mrz_data
        
    except Exception as e:
        print(f"❌ Error during MRZ parsing: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_full_ocr_validation(image_path: str):
    """Test the full OCR validation pipeline"""
    print_section("Step 4: Full OCR Validation Pipeline")
    
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return None
    
    try:
        print(f"📄 Loading image: {image_path}")
        pil_image = Image.open(image_path)
        print(f"✅ Image loaded: {pil_image.size[0]}x{pil_image.size[1]} {pil_image.mode}")
        
        print("\n🔄 Running full OCR validation...")
        result = validate_document_ocr(pil_image)
        
        print("\n📊 Validation Result:")
        print("-" * 70)
        print(f"  Valid: {result.get('valid', False)}")
        if result.get('error'):
            print(f"  Error: {result['error']}")
        if result.get('details'):
            print(f"  Details:")
            for detail in result['details']:
                print(f"    - {detail}")
        if result.get('mrz_data') and not result['mrz_data'].get('error'):
            print(f"\n  MRZ Data:")
            for key, value in result['mrz_data'].items():
                if key != 'error':
                    print(f"    {key}: {value}")
        print("-" * 70)
        
        return result
        
    except Exception as e:
        print(f"❌ Error during full OCR validation: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main test function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Debug OCR process step by step")
    parser.add_argument(
        "image",
        type=str,
        help="Path to document image (passport/ID)"
    )
    parser.add_argument(
        "--no-debug",
        action="store_true",
        help="Don't save debug images"
    )
    parser.add_argument(
        "--step",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="Run only a specific step (1=MRZ extraction, 2=OCR, 3=parsing, 4=full, 5=all)"
    )
    
    args = parser.parse_args()
    
    debug = not args.no_debug
    image_path = args.image
    
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        sys.exit(1)
    
    print_section("OCR Debug Test")
    print(f"Image: {image_path}")
    print(f"Debug mode: {debug}")
    
    # Step 1: MRZ Extraction (file path method)
    if args.step is None or args.step == 1 or args.step == 5:
        mrz_image = test_mrz_extraction(image_path, debug=debug)
        
        # Step 1b: MRZ Extraction (PIL method - as used in service)
        if mrz_image is not None:
            mrz_image_pil = test_mrz_extraction_from_pil(image_path)
        else:
            mrz_image_pil = None
            print("\n⚠️  Skipping PIL method test (MRZ extraction failed)")
    else:
        mrz_image = None
        mrz_image_pil = None
    
    # Step 2: OCR Text Extraction
    if args.step is None or args.step == 2 or args.step == 5:
        if mrz_image is not None:
            mrz_text = test_ocr_text_extraction(mrz_image)
        else:
            mrz_text = None
            print("\n⚠️  Skipping OCR text extraction (no MRZ image)")
    else:
        mrz_text = None
    
    # Step 3: MRZ Parsing
    if args.step is None or args.step == 3 or args.step == 5:
        if mrz_text:
            mrz_data = test_mrz_parsing(mrz_text)
        else:
            mrz_data = None
            print("\n⚠️  Skipping MRZ parsing (no MRZ text)")
    else:
        mrz_data = None
    
    # Step 4: Full Pipeline
    if args.step is None or args.step == 4 or args.step == 5:
        full_result = test_full_ocr_validation(image_path)
    else:
        full_result = None
    
    # Summary
    print_section("Test Summary")
    
    results = {
        "MRZ Extraction": mrz_image is not None,
        "MRZ Extraction (PIL)": mrz_image_pil is not None if 'mrz_image_pil' in locals() else None,
        "OCR Text Extraction": mrz_text is not None,
        "MRZ Parsing": mrz_data is not None and "error" not in mrz_data if mrz_data else False,
        "Full Validation": full_result.get("valid", False) if full_result else False
    }
    
    for step, passed in results.items():
        if passed is None:
            status = "⏭️  SKIPPED"
        elif passed:
            status = "✅ PASSED"
        else:
            status = "❌ FAILED"
        print(f"  {step}: {status}")
    
    # Exit code
    if all(v for v in results.values() if v is not None):
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed - check the output above for details")
        sys.exit(1)

if __name__ == "__main__":
    main()
