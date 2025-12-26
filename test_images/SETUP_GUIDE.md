# Image Validator Test Images - Setup Guide

## Quick Setup

### Step 1: Create the Directory Structure

The directories have been created for you:
- `test_images/valid/` - For valid test images
- `test_images/invalid/` - For invalid test images

### Step 2: Add Your Test Images

You need **at least 10 images total** (5 valid + 5 invalid minimum).
For full testing including gesture and content safety, add 5 more invalid images (10 invalid total).

## Valid Images (5 images - should PASS)

Place these in `test_images/valid/`:

1. **valid_01_clear_face.jpg**
   - Clear, front-facing photo of a child
   - Good lighting, not blurry
   - Exactly 1 face visible
   - At least 200x200 pixels

2. **valid_02_smiling.jpg**
   - Child smiling, happy expression
   - Good lighting
   - Clear face visible

3. **valid_03_outdoor.jpg**
   - Child outdoors with natural lighting
   - Clear face, good quality

4. **valid_04_indoor.jpg**
   - Child indoors with good lighting
   - Clear face, not too dark or bright

5. **valid_05_different_angle.jpg**
   - Child at slight angle (not completely front-facing)
   - Face still clearly visible
   - Good quality

## Invalid Images (5 images - should FAIL)

Place these in `test_images/invalid/`:

1. **invalid_01_no_face.jpg**
   - Image with NO face
   - Examples: landscape, object, animal, abstract image
   - Should fail: "Please upload a clear photo with one face visible"

2. **invalid_02_multiple_faces.jpg**
   - Image with 2 or more people
   - Examples: group photo, family photo, two children
   - Should fail: "Please upload a clear photo with one face visible"

3. **invalid_03_too_blurry.jpg**
   - Very blurry photo of a child
   - Motion blur or out-of-focus
   - Should fail: "Image quality is too low. Please upload a clearer photo"

4. **invalid_04_too_dark.jpg**
   - Very dark or underexposed photo
   - Face barely visible due to darkness
   - Should fail: "Image quality is too low. Please upload a clearer photo"

5. **invalid_05_too_small.jpg**
   - Very low resolution image
   - Less than 200x200 pixels (e.g., 150x150 or 100x100)
   - Should fail: "Image quality is too low. Please upload a clearer photo"
   - **Note**: Make sure the image is actually small! Use an image editor to resize an image to be less than 200x200 pixels

### Additional Invalid Images (for gesture and content safety):

6. **invalid_06_fingers_near_face.jpg**
   - Child with fingers near face (picking nose, etc.)
   - Should fail: "Please upload a photo with appropriate pose (no hands near face)"
   - **Note**: Requires MediaPipe or OpenCV for hand detection

7. **invalid_07_hand_in_mouth.jpg**
   - Child with hand/fingers in or near mouth
   - Should fail: "Please upload a photo with appropriate pose (no hands near face)"

8. **invalid_08_inappropriate_gesture.jpg**
   - Child making inappropriate gesture
   - Should fail: "Image content not appropriate for children's book"
   - **Note**: Requires OpenAI API key for content moderation

9. **invalid_09_nudity.jpg**
   - Image with nudity or inappropriate exposure
   - Should fail: "Image content not appropriate for children's book"
   - **Note**: Requires OpenAI API key. Use appropriate test images (stock photos, etc.)

10. **invalid_10_inappropriate_pose.jpg**
    - Child in inappropriate pose
    - Should fail: "Image content not appropriate for children's book"

### Alternative Invalid Images (if you want more):

11. **invalid_11_too_bright.jpg** - Overexposed/washed out photo
12. **invalid_12_low_contrast.jpg** - Very low contrast (almost grayscale)
13. **invalid_13_side_profile.jpg** - Extreme side angle where face isn't clearly visible

## Where to Get Test Images

### For Valid Images:
- Use photos you have permission to use
- Stock photo sites (with appropriate licenses):
  - Unsplash (unsplash.com) - free, high quality
  - Pexels (pexels.com) - free stock photos
  - Pixabay (pixabay.com) - free images
- **Important**: Ensure you have permission to use children's photos

### For Invalid Images:
- **No face**: Use any landscape, object, or abstract image
- **Multiple faces**: Use any group photo or family photo
- **Too blurry**: Take a blurry photo or use image editing to add blur
- **Too dark**: Use image editing to darken a photo
- **Too small**: Resize an image to be very small (< 200x200)
- **Fingers near face**: Use stock photos or photos you have permission to use showing inappropriate gestures
- **Inappropriate gestures/nudity**: Use stock photos from moderation test image sets, or create synthetic test images
  - **Important**: Only use images you have permission to use for testing purposes
  - Consider using AI-generated test images for sensitive content

## Testing Your Images

Once you've added your images, run:

```bash
python test_image_validator.py
```

This will:
- Test all images in `test_images/valid/` (should all pass)
- Test all images in `test_images/invalid/` (should all fail)
- Show you which images passed/failed and why

## Expected Results

When you run the test, you should see:

```
Testing VALID Images (should PASS):
  valid_01_clear_face.jpg     -> ✓ PASSED
  valid_02_smiling.jpg       -> ✓ PASSED
  valid_03_outdoor.jpg       -> ✓ PASSED
  valid_04_indoor.jpg         -> ✓ PASSED
  valid_05_different_angle.jpg -> ✓ PASSED

Testing INVALID Images (should FAIL):
  invalid_01_no_face.jpg      -> ✓ FAILED (correct)
  invalid_02_multiple_faces.jpg -> ✓ FAILED (correct)
  invalid_03_too_blurry.jpg   -> ✓ FAILED (correct)
  invalid_04_too_dark.jpg     -> ✓ FAILED (correct)
  invalid_05_too_small.jpg    -> ✓ FAILED (correct)
```

## Troubleshooting

### "No images found"
- Make sure images are in the correct directories
- Check file extensions: .jpg, .jpeg, .png, or .webp
- Verify the directory structure exists

### Valid images are being rejected
- Check that face detection libraries are installed: `pip install opencv-python face-recognition`
- Verify the image has exactly 1 clear face
- Check image quality (not too blurry, good lighting)
- Make sure hands/fingers are not near the face

### Invalid images are being accepted
- This might be expected if detection libraries aren't installed
- Install OpenCV: `pip install opencv-python`
- For better accuracy, install: `pip install face-recognition`
- For hand detection: `pip install mediapipe`
- For content moderation: Make sure `OPENAI_API_KEY` is set in `.env`

### Hand detection not working
- Install MediaPipe for better accuracy: `pip install mediapipe`
- OpenCV has basic skin detection as fallback, but MediaPipe is more accurate
- Check logs for hand detection errors

### Content moderation not working
- Make sure `OPENAI_API_KEY` is set in your `.env` file
- Check that OpenAI Vision API is accessible
- Review logs for moderation API errors

## File Naming

Use descriptive names:
- Valid: `valid_01_clear_face.jpg`, `valid_02_smiling.jpg`, etc.
- Invalid: `invalid_01_no_face.jpg`, `invalid_02_multiple_faces.jpg`, etc.

The test script will find any image files regardless of name, but descriptive names help you organize them.

## Privacy & Permissions

⚠️ **Important:**
- Only use images you have permission to use
- For children's photos, ensure you have parental consent
- Consider using stock photos or creating synthetic test images
- Never commit real children's photos to version control without proper consent
- Add `test_images/` to `.gitignore` if you're using real photos

