# Image Validator Enhancements

## Summary

Enhanced the image validator to detect inappropriate gestures (fingers near face, picking nose, etc.) and inappropriate content (nudity, inappropriate poses) using advanced detection methods.

## New Features

### 1. Hand Detection for Inappropriate Gestures

**What it detects:**
- Fingers near face (picking nose, touching face)
- Hands in or near mouth
- Any hand/finger proximity to face region

**How it works:**
- **Primary**: Uses MediaPipe for accurate hand and finger tracking
- **Fallback**: Uses OpenCV skin detection if MediaPipe is not available
- Detects hand landmarks and checks proximity to face region
- Rejects images where hands/fingers are too close to the face

**Error message:**
```
"Please upload a photo with appropriate pose (no hands near face)"
```

**Installation:**
```bash
pip install mediapipe  # For best accuracy
# OR
pip install opencv-python  # Basic fallback (already in requirements.txt)
```

### 2. Content Safety Moderation

**What it detects:**
- Nudity or inappropriate exposure
- Inappropriate gestures or poses
- Any content not suitable for children's books

**How it works:**
- Uses OpenAI Vision API (gpt-4o-mini by default) to analyze images
- Sends image to OpenAI with a moderation prompt
- Returns "SAFE" or "UNSAFE" based on content analysis
- Automatically rejects images flagged as unsafe

**Error message:**
```
"Image content not appropriate for children's book"
```

**Requirements:**
- `OPENAI_API_KEY` must be set in `.env` file
- OpenAI Vision API access (included with OpenAI API key)

## Updated Files

1. **`image_validator.py`**
   - Added `_check_hands_near_face()` function for hand detection
   - Enhanced `_check_pose_appropriateness()` to use hand detection
   - Completely rewrote `_check_content_safety()` to use OpenAI Vision API
   - Added MediaPipe import and detection logic
   - Added OpenCV fallback for hand detection

2. **`requirements.txt`**
   - Added `mediapipe>=0.10.0` for hand detection

3. **`test_images/README.md`**
   - Updated with new invalid image types (gestures, nudity)
   - Added documentation for 10 invalid image types

4. **`test_images/SETUP_GUIDE.md`**
   - Updated with new invalid image requirements
   - Added troubleshooting for hand detection and content moderation

## Test Images Needed

### New Invalid Image Types:

6. **invalid_06_fingers_near_face.jpg** - Child with fingers near face
7. **invalid_07_hand_in_mouth.jpg** - Child with hand/fingers in mouth
8. **invalid_08_inappropriate_gesture.jpg** - Inappropriate gesture
9. **invalid_09_nudity.jpg** - Nudity/inappropriate exposure
10. **invalid_10_inappropriate_pose.jpg** - Inappropriate pose

## How It Works

### Hand Detection Flow:

1. **MediaPipe (if available):**
   - Detects hand landmarks (fingertips, palm)
   - Gets face region from face detection
   - Calculates distance between fingertips and face
   - Rejects if fingertips are within proximity threshold

2. **OpenCV Fallback (if MediaPipe not available):**
   - Uses skin color detection in HSV color space
   - Detects face region
   - Checks for skin-colored pixels near face
   - Uses heuristic to determine if hands are present

### Content Moderation Flow:

1. Load and prepare image (resize if needed)
2. Encode image to base64
3. Send to OpenAI Vision API with moderation prompt
4. Parse response ("SAFE" or "UNSAFE")
5. Reject if unsafe, accept if safe

## Configuration

### Environment Variables:

- `OPENAI_API_KEY` - Required for content moderation
- `MODEL_VISION` - Optional, defaults to "gpt-4o-mini" (cheaper model)

### Detection Libraries:

- **MediaPipe** (recommended): `pip install mediapipe`
- **OpenCV** (fallback): `pip install opencv-python` (already in requirements.txt)
- **face_recognition** (optional): `pip install face-recognition` (for better face detection)

## Testing

Run the test script to verify all validations:

```bash
python test_image_validator.py
```

This will test:
- Face detection
- Image quality
- Hand/gesture detection (if libraries installed)
- Content moderation (if OpenAI API key set)

## Limitations

1. **Hand Detection:**
   - MediaPipe provides best accuracy
   - OpenCV fallback is less accurate (uses skin color heuristics)
   - May have false positives/negatives depending on image quality

2. **Content Moderation:**
   - Requires OpenAI API key and API access
   - Uses Vision API which has costs per image
   - May have false positives (rejecting safe images)
   - Response time depends on API latency

3. **Privacy:**
   - Images are sent to OpenAI for moderation
   - Review OpenAI's privacy policy for data handling
   - Consider using local moderation solutions for production

## Future Improvements

1. **Local Content Moderation:**
   - Use local ML models instead of API calls
   - Faster and more private
   - No API costs

2. **Better Hand Detection:**
   - Fine-tune proximity thresholds
   - Add gesture classification (picking nose vs. waving)
   - Improve accuracy for edge cases

3. **Caching:**
   - Cache moderation results for identical images
   - Reduce API calls and costs

## Notes

- Hand detection gracefully degrades if libraries aren't installed
- Content moderation is skipped if OpenAI API key is not set
- All checks are lenient on errors (don't block users unnecessarily)
- Logs warnings for debugging and monitoring

