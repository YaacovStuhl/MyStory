"""
Test script for image validator using sample images.

This script tests the image validator against sample images in test_images/ directory.
"""

import os
import sys
from pathlib import Path
from image_validator import validate_image

# Directory paths
BASE_DIR = Path(__file__).parent
VALID_DIR = BASE_DIR / "test_images" / "valid"
INVALID_DIR = BASE_DIR / "test_images" / "invalid"


def test_image_validator():
    """Test image validator with sample images."""
    print("=" * 70)
    print("Image Validator Test Suite")
    print("=" * 70)
    print()
    
    # Check if directories exist
    if not VALID_DIR.exists():
        print(f"⚠️  Valid images directory not found: {VALID_DIR}")
        print("   Creating directory...")
        VALID_DIR.mkdir(parents=True, exist_ok=True)
        print("   Please add 5 valid images to this directory")
        print()
    
    if not INVALID_DIR.exists():
        print(f"⚠️  Invalid images directory not found: {INVALID_DIR}")
        print("   Creating directory...")
        INVALID_DIR.mkdir(parents=True, exist_ok=True)
        print("   Please add 5 invalid images to this directory")
        print()
    
    # Test valid images
    print("Testing VALID Images (should PASS):")
    print("-" * 70)
    valid_images = list(VALID_DIR.glob("*.jpg")) + list(VALID_DIR.glob("*.jpeg")) + \
                   list(VALID_DIR.glob("*.png")) + list(VALID_DIR.glob("*.webp"))
    
    if not valid_images:
        print("   No valid images found in test_images/valid/")
        print("   Please add 5 valid images to test the validator")
    else:
        valid_passed = 0
        valid_failed = 0
        
        for img_path in sorted(valid_images):
            is_valid, error = validate_image(str(img_path))
            status = "✓ PASSED" if is_valid else "✗ FAILED (ERROR!)"
            print(f"   {img_path.name:40} -> {status}")
            if is_valid:
                valid_passed += 1
            else:
                valid_failed += 1
                print(f"      Error: {error}")
        
        print()
        print(f"   Results: {valid_passed} passed, {valid_failed} failed out of {len(valid_images)} images")
    
    print()
    
    # Test invalid images
    print("Testing INVALID Images (should FAIL):")
    print("-" * 70)
    invalid_images = list(INVALID_DIR.glob("*.jpg")) + list(INVALID_DIR.glob("*.jpeg")) + \
                         list(INVALID_DIR.glob("*.png")) + list(INVALID_DIR.glob("*.webp"))
    
    if not invalid_images:
        print("   No invalid images found in test_images/invalid/")
        print("   Please add 5 invalid images to test the validator")
    else:
        invalid_passed = 0
        invalid_failed = 0
        
        for img_path in sorted(invalid_images):
            is_valid, error = validate_image(str(img_path))
            status = "✓ FAILED (correct)" if not is_valid else "✗ PASSED (ERROR!)"
            print(f"   {img_path.name:40} -> {status}")
            if not is_valid:
                invalid_failed += 1
                print(f"      Rejected with: {error}")
            else:
                invalid_passed += 1
                print(f"      ⚠️  WARNING: This image was accepted but should be rejected!")
        
        print()
        print(f"   Results: {invalid_failed} correctly rejected, {invalid_passed} incorrectly accepted out of {len(invalid_images)} images")
    
    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    
    if valid_images and invalid_images:
        total_valid = len(valid_images)
        total_invalid = len(invalid_images)
        valid_passed_count = sum(1 for img in valid_images if validate_image(str(img))[0])
        invalid_failed_count = sum(1 for img in invalid_images if not validate_image(str(img))[0])
        
        print(f"Valid images: {valid_passed_count}/{total_valid} passed")
        print(f"Invalid images: {invalid_failed_count}/{total_invalid} correctly rejected")
        print()
        
        if valid_passed_count == total_valid and invalid_failed_count == total_invalid:
            print("✓ All tests passed! Validator is working correctly.")
        else:
            print("⚠️  Some tests failed. Review the results above.")
            if valid_passed_count < total_valid:
                print(f"   - {total_valid - valid_passed_count} valid image(s) were incorrectly rejected")
            if invalid_failed_count < total_invalid:
                print(f"   - {total_invalid - invalid_failed_count} invalid image(s) were incorrectly accepted")
    else:
        print("⚠️  Please add test images to run full tests:")
        print(f"   - Add 5 valid images to: {VALID_DIR}")
        print(f"   - Add 5 invalid images to: {INVALID_DIR}")
    
    print()


def list_required_images():
    """List what images are needed for testing."""
    print("=" * 70)
    print("Required Test Images")
    print("=" * 70)
    print()
    print("VALID Images (should pass validation):")
    print("  1. valid_01_clear_face.jpg - Clear front-facing photo of a child")
    print("  2. valid_02_smiling.jpg - Child smiling, good lighting")
    print("  3. valid_03_outdoor.jpg - Child outdoors, natural lighting")
    print("  4. valid_04_indoor.jpg - Child indoors, good lighting")
    print("  5. valid_05_different_angle.jpg - Child at slight angle, still clear face")
    print()
    print("INVALID Images (should fail validation):")
    print("  1. invalid_01_no_face.jpg - Image with no face (landscape/object)")
    print("  2. invalid_02_multiple_faces.jpg - Image with 2+ people")
    print("  3. invalid_03_too_blurry.jpg - Very blurry photo")
    print("  4. invalid_04_too_dark.jpg - Very dark/underexposed photo")
    print("  5. invalid_05_too_small.jpg - Very low resolution (< 200x200)")
    print()
    print(f"Place valid images in: {VALID_DIR}")
    print(f"Place invalid images in: {INVALID_DIR}")
    print()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        list_required_images()
    else:
        test_image_validator()

