# Image Validator Test Images

This directory contains sample images for testing the image validator.

## Directory Structure

```
test_images/
├── valid/          # 5 valid images that should pass all checks
├── invalid/        # 5 invalid images that should fail validation
└── README.md       # This file
```

## Valid Images (should PASS validation)

Each valid image should have:
- ✅ Exactly 1 face clearly visible
- ✅ Good image quality (not blurry)
- ✅ Good lighting (not too dark or too bright)
- ✅ Adequate resolution (at least 200x200 pixels)
- ✅ Good contrast
- ✅ Appropriate pose for a children's book
- ✅ G-rated content

### Suggested Valid Images:

1. **valid_01_clear_face.jpg** - Clear front-facing photo of a child
2. **valid_02_smiling.jpg** - Child smiling, good lighting
3. **valid_03_outdoor.jpg** - Child outdoors, natural lighting
4. **valid_04_indoor.jpg** - Child indoors, good lighting
5. **valid_05_different_angle.jpg** - Child at slight angle, still clear face

## Invalid Images (should FAIL validation)

Each invalid image should fail a specific check:

### Required Invalid Images (5 minimum):

1. **invalid_01_no_face.jpg** - Image with no face (e.g., landscape, object, animal)
   - Should fail: Face detection (0 faces)
   - Error: "Please upload a clear photo with one face visible"

2. **invalid_02_multiple_faces.jpg** - Image with 2+ people
   - Should fail: Face detection (multiple faces)
   - Error: "Please upload a clear photo with one face visible"

3. **invalid_03_too_blurry.jpg** - Very blurry photo of a child
   - Should fail: Image quality (blur detection)
   - Error: "Image quality is too low. Please upload a clearer photo"

4. **invalid_04_too_dark.jpg** - Very dark/underexposed photo
   - Should fail: Image quality (brightness check)
   - Error: "Image quality is too low. Please upload a clearer photo"

5. **invalid_05_too_small.jpg** - Very low resolution image (< 200x200)
   - Should fail: Image quality (resolution check)
   - Error: "Image quality is too low. Please upload a clearer photo"

### Additional Invalid Images (for gesture and content safety):

6. **invalid_06_fingers_near_face.jpg** - Child with fingers near face (picking nose, etc.)
   - Should fail: Pose appropriateness (hand detection)
   - Error: "Please upload a photo with appropriate pose (no hands near face)"
   - **Note**: Requires MediaPipe or OpenCV for hand detection

7. **invalid_07_hand_in_mouth.jpg** - Child with hand/fingers in or near mouth
   - Should fail: Pose appropriateness (hand detection)
   - Error: "Please upload a photo with appropriate pose (no hands near face)"

8. **invalid_08_inappropriate_gesture.jpg** - Child making inappropriate gesture
   - Should fail: Content safety (OpenAI moderation)
   - Error: "Image content not appropriate for children's book"
   - **Note**: Requires OpenAI API key for content moderation

9. **invalid_09_nudity.jpg** - Image with nudity or inappropriate exposure
   - Should fail: Content safety (OpenAI moderation)
   - Error: "Image content not appropriate for children's book"
   - **Note**: Requires OpenAI API key. Use appropriate test images (stock photos, etc.)

10. **invalid_10_inappropriate_pose.jpg** - Child in inappropriate pose
    - Should fail: Content safety (OpenAI moderation)
    - Error: "Image content not appropriate for children's book"

### Alternative Invalid Images:

- **invalid_11_too_bright.jpg** - Overexposed/washed out photo
- **invalid_12_low_contrast.jpg** - Very low contrast image
- **invalid_13_side_profile.jpg** - Face not clearly visible (extreme side angle)

## How to Add Your Test Images

1. **Find or create test images:**
   - Use photos you have permission to use
   - For valid images: Use clear photos of children (with permission)
   - For invalid images: You can use stock photos, objects, or create test images

2. **Name your images:**
   - Valid: `valid_01_clear_face.jpg`, `valid_02_smiling.jpg`, etc.
   - Invalid: `invalid_01_no_face.jpg`, `invalid_02_multiple_faces.jpg`, etc.

3. **Place them in the correct directory:**
   - Valid images → `test_images/valid/`
   - Invalid images → `test_images/invalid/`

4. **Run the test script:**
   ```bash
   python test_image_validator.py
   ```

## Important Notes

⚠️ **Privacy & Permissions:**
- Only use images you have permission to use
- For children's photos, ensure you have parental consent
- Consider using stock photos or creating synthetic test images
- Never commit real children's photos to version control without proper consent

⚠️ **File Formats:**
- Supported formats: JPG, JPEG, PNG, WEBP
- Use common formats for best compatibility

⚠️ **Image Sizes:**
- Valid images should be at least 200x200 pixels
- Recommended: 500x500 to 2000x2000 pixels
- Keep file sizes reasonable (< 5MB per image)

## Testing the Validator

Run the test script to validate all sample images:

```bash
python test_image_validator.py
```

This will:
- Test all images in `test_images/valid/` (should all pass)
- Test all images in `test_images/invalid/` (should all fail)
- Report any mismatches (images that passed when they should fail, or vice versa)

