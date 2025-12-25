"""
Image validation module for child photos.
Validates that uploaded images are suitable for children's book generation.
"""

import os
import logging
import base64
import io
from typing import Tuple, Optional
from PIL import Image
import numpy as np

# Try to import face_recognition
try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    logging.warning("[image_validator] face_recognition not installed. Face detection will use OpenCV fallback.")

# Try to import OpenCV
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    logging.warning("[image_validator] OpenCV not installed. Some validation features will be limited.")

# Try to import MediaPipe for hand detection (better than OpenCV for hand tracking)
try:
    import mediapipe as mp
    # Check if using old API (solutions) or new API (tasks)
    try:
        from mediapipe.tasks.python import vision as mp_vision
        from mediapipe import tasks
        MEDIAPIPE_AVAILABLE = True
        MEDIAPIPE_USE_TASKS_API = True
    except ImportError:
        # Try old API
        try:
            mp.solutions.hands  # This will fail if solutions doesn't exist
            MEDIAPIPE_AVAILABLE = True
            MEDIAPIPE_USE_TASKS_API = False
        except AttributeError:
            MEDIAPIPE_AVAILABLE = False
            MEDIAPIPE_USE_TASKS_API = False
            logging.warning("[image_validator] MediaPipe installed but incompatible version. Hand detection will use OpenCV fallback or be skipped.")
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    MEDIAPIPE_USE_TASKS_API = False
    logging.info("[image_validator] MediaPipe not installed. Hand detection will use OpenCV fallback or be skipped.")


def validate_image(image_path: str) -> Tuple[bool, Optional[str]]:
    """
    Validate an uploaded image for children's book generation.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if image is valid, False otherwise
        - error_message: Error message if invalid, None if valid
    """
    try:
        # Load image
        img = Image.open(image_path)
        img_array = np.array(img)
        
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
            img_array = np.array(img)
        
        # 1. Face Detection - exactly 1 face
        face_result, face_error = _check_face_detection(image_path, img_array)
        if not face_result:
            return False, face_error
        
        # 2. Child Detection - verify the face belongs to a child
        child_result, child_error = _check_is_child(image_path, img_array)
        if not child_result:
            return False, child_error
        
        # 3. Image Quality - not blurry, good lighting
        quality_result, quality_error = _check_image_quality(img_array)
        if not quality_result:
            return False, quality_error
        
        # 4. Inappropriate Pose - basic checks
        pose_result, pose_error = _check_pose_appropriateness(image_path, img_array)
        if not pose_result:
            return False, pose_error
        
        # 5. Content Safety - G-rated
        safety_result, safety_error = _check_content_safety(image_path)
        if not safety_result:
            return False, safety_error
        
        return True, None
        
    except Exception as e:
        logging.error(f"[image_validator] Error validating image: {e}")
        return False, "Error processing image. Please try again with a different photo."


def _check_face_detection(image_path: str, img_array: np.ndarray) -> Tuple[bool, Optional[str]]:
    """Check that exactly 1 human face is present."""
    try:
        if FACE_RECOGNITION_AVAILABLE:
            # Use face_recognition library (more accurate)
            face_locations = face_recognition.face_locations(img_array)
            num_faces = len(face_locations)
            
            if num_faces == 0:
                return False, "Please upload a clear photo with one face visible"
            elif num_faces > 1:
                return False, "Please upload a clear photo with one face visible"
            else:
                return True, None
                
        elif OPENCV_AVAILABLE:
            # Fallback to OpenCV face detection
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            num_faces = len(faces)
            
            if num_faces == 0:
                return False, "Please upload a clear photo with one face visible"
            elif num_faces > 1:
                return False, "Please upload a clear photo with one face visible"
            else:
                return True, None
        else:
            # No face detection available - this is a critical check, so we must fail
            logging.error("[image_validator] Face detection libraries not available. Please install face_recognition or opencv-python.")
            return False, "Image validation requires face detection. Please install required libraries (face_recognition or opencv-python)."
            
    except Exception as e:
        logging.error(f"[image_validator] Face detection error: {e}")
        # On error, be lenient - don't block the user
        return True, None


def _check_is_child(image_path: str, img_array: np.ndarray) -> Tuple[bool, Optional[str]]:
    """Check that the image contains a child (not an adult)."""
    try:
        # Use OpenAI Vision API to verify the image contains a child
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            # No API key - skip child check (but warn)
            logging.warning("[image_validator] OpenAI API key not available, skipping child detection check")
            return True, None  # Be lenient if API key not available
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_api_key)
            
            # Read and prepare image
            img = Image.open(image_path)
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            # Resize if very large to reduce API costs
            max_size = 1024
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size), Image.LANCZOS)
            
            # Save to bytes buffer
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            buffer.seek(0)
            image_data = buffer.read()
            
            # Encode to base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            
            # Use OpenAI Vision API to check if image contains a child
            model = os.getenv("MODEL_VISION", "gpt-4o-mini")  # Use cheaper model
            
            child_check_prompt = """Analyze this image and determine if it contains a CHILD (age 12 or under).

Respond with ONLY one word:
- "CHILD" if the image clearly shows a child (age 12 or under)
- "ADULT" if the image shows an adult, teenager (13+), or no person
- "UNCLEAR" if you cannot determine

Be strict - if there's any doubt about age, respond "ADULT"."""
            
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": child_check_prompt
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_b64}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=10,
                    temperature=0.1  # Low temperature for consistent results
                )
                
                result_text = response.choices[0].message.content.strip().upper()
                
                if "CHILD" in result_text:
                    return True, None
                elif "ADULT" in result_text or "UNCLEAR" in result_text:
                    logging.warning(f"[image_validator] Child detection check failed: {result_text}")
                    return False, "Please upload a photo of a child (age 12 or under)"
                else:
                    # Unexpected response - be cautious and reject
                    logging.warning(f"[image_validator] Unexpected child detection response: {result_text}")
                    return False, "Please upload a photo of a child (age 12 or under)"
                    
            except Exception as api_error:
                logging.error(f"[image_validator] OpenAI API error during child detection: {api_error}")
                # On API error, be lenient - don't block the user
                return True, None
                
        except ImportError:
            logging.warning("[image_validator] OpenAI library not available, skipping child detection check")
            return True, None
            
    except Exception as e:
        logging.error(f"[image_validator] Child detection error: {e}")
        # On error, be lenient - don't block users
        return True, None


def _check_image_quality(img_array: np.ndarray) -> Tuple[bool, Optional[str]]:
    """Check image quality: resolution, blur, brightness."""
    try:
        height, width = img_array.shape[:2]
        
        # Check minimum resolution
        min_resolution = 200  # Minimum width or height
        if width < min_resolution or height < min_resolution:
            return False, "Image quality is too low. Please upload a clearer photo"
        
        if OPENCV_AVAILABLE:
            # Convert to grayscale for analysis
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array
            
            # Check blur using Laplacian variance
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            blur_threshold = 100  # Lower values indicate more blur
            if laplacian_var < blur_threshold:
                return False, "Image quality is too low. Please upload a clearer photo"
            
            # Check brightness (average pixel value)
            mean_brightness = np.mean(gray)
            # Good lighting: between 50 and 200 (out of 255)
            if mean_brightness < 50:
                return False, "Image quality is too low. Please upload a clearer photo"
            if mean_brightness > 240:
                return False, "Image quality is too low. Please upload a clearer photo"
            
            # Check contrast (standard deviation)
            contrast = np.std(gray)
            if contrast < 20:  # Very low contrast
                return False, "Image quality is too low. Please upload a clearer photo"
        
        return True, None
        
    except Exception as e:
        logging.error(f"[image_validator] Quality check error: {e}")
        # On error, be lenient
        return True, None


def _check_pose_appropriateness(image_path: str, img_array: np.ndarray) -> Tuple[bool, Optional[str]]:
    """Check for inappropriate poses (fingers near face, picking nose, tongue out, etc.)."""
    try:
        # Check for hands/fingers near face using MediaPipe or OpenCV
        hand_near_face = _check_hands_near_face(img_array)
        logging.info(f"[image_validator] Hand detection result: {hand_near_face}")
        if hand_near_face:
            return False, "Please upload a photo with appropriate pose (no hands near face)"
        
        # If hand detection couldn't determine (returned None), use OpenAI Vision API as fallback
        if hand_near_face is None:
            logging.info("[image_validator] Hand detection returned None, using Vision API fallback")
            hand_check_result = _check_hands_near_face_vision_api(image_path)
            logging.info(f"[image_validator] Vision API hand check result: {hand_check_result}")
            if hand_check_result is True:  # True means hands detected near face
                return False, "Please upload a photo with appropriate pose (no hands near face)"
        
        if FACE_RECOGNITION_AVAILABLE:
            # Get face landmarks
            face_landmarks_list = face_recognition.face_landmarks(img_array)
            
            if len(face_landmarks_list) == 0:
                # No face detected - this should have been caught earlier, but be lenient
                return True, None
            
            # Get landmarks for the first (and should be only) face
            landmarks = face_landmarks_list[0]
            
            # Check for tongue out (mouth open with tongue visible)
            # This is a simplified check - in production, you might use more sophisticated ML models
            top_lip = landmarks.get('top_lip', [])
            bottom_lip = landmarks.get('bottom_lip', [])
            
            if top_lip and bottom_lip:
                # Calculate mouth opening
                top_y = np.mean([point[1] for point in top_lip])
                bottom_y = np.mean([point[1] for point in bottom_lip])
                mouth_opening = bottom_y - top_y
                
                # If mouth is very open, might be inappropriate
                # This is a heuristic - adjust threshold as needed
                if mouth_opening > 30:  # Threshold in pixels
                    # Could be tongue out or inappropriate pose
                    # For now, we'll be lenient and allow it
                    # In production, you might want stricter checks
                    pass
            
            # Check for nose picking gesture
            # Get nose tip and check if there are hand landmarks near it
            nose_tip = landmarks.get('nose_tip', [])
            if nose_tip and hand_near_face is None:
                # If we couldn't detect hands, we can't check for nose picking
                # But we already checked hand_near_face above, so if we get here, it's OK
                pass
            
        # Basic checks passed
        return True, None
        
    except Exception as e:
        logging.error(f"[image_validator] Pose check error: {e}")
        # On error, be lenient - don't block users
        return True, None


def _check_hands_near_face(img_array: np.ndarray) -> Optional[bool]:
    """
    Check if hands/fingers are near the face (indicating inappropriate gestures).
    Returns True if hands detected near face, False if hands detected but not near face, None if can't detect.
    """
    try:
        if MEDIAPIPE_AVAILABLE and MEDIAPIPE_USE_TASKS_API:
            # Use MediaPipe Tasks API (newer versions)
            try:
                from mediapipe.tasks.python import vision as mp_vision
                from mediapipe import tasks
                
                # MediaPipe Tasks API requires a model file - skip for now
                # Users should install opencv-python for hand detection fallback
                logging.info("[image_validator] MediaPipe Tasks API requires model file. Hand detection will use OpenCV fallback or be skipped.")
                results = None
                
            except Exception as e:
                logging.warning(f"[image_validator] MediaPipe Tasks API error: {e}, falling back to OpenCV")
                results = None
                
        elif MEDIAPIPE_AVAILABLE and not MEDIAPIPE_USE_TASKS_API:
            # Use MediaPipe Solutions API (older versions)
            try:
                mp_hands = mp.solutions.hands
                
                with mp_hands.Hands(
                    static_image_mode=True,
                    max_num_hands=2,
                    min_detection_confidence=0.5
                ) as hands:
                    # MediaPipe expects RGB images
                    results = hands.process(img_array)
                
                if not results or not results.multi_hand_landmarks:
                    # No hands detected - this is fine
                    return False
            except Exception as e:
                logging.warning(f"[image_validator] MediaPipe Solutions API error: {e}, falling back to OpenCV")
                results = None
        else:
            results = None
        
        # If we have hand detection results, check proximity to face
        if results and hasattr(results, 'multi_hand_landmarks') and results.multi_hand_landmarks:
            # Get face location using face_recognition or OpenCV
            face_region = None
            if FACE_RECOGNITION_AVAILABLE:
                face_locations = face_recognition.face_locations(img_array)
                if face_locations:
                    # Get the first face location (top, right, bottom, left)
                    top, right, bottom, left = face_locations[0]
                    face_region = {
                        'x_min': left,
                        'x_max': right,
                        'y_min': top,
                        'y_max': bottom,
                        'center_x': (left + right) / 2,
                        'center_y': (top + bottom) / 2
                    }
            elif OPENCV_AVAILABLE:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
                faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
                if len(faces) > 0:
                    x, y, w, h = faces[0]
                    face_region = {
                        'x_min': x,
                        'x_max': x + w,
                        'y_min': y,
                        'y_max': y + h,
                        'center_x': x + w / 2,
                        'center_y': y + h / 2
                    }
            
            if not face_region:
                # Can't detect face, can't check hand proximity
                return None
            
            # Check each detected hand
            height, width = img_array.shape[:2]
            for hand_landmarks in results.multi_hand_landmarks:
                # Get hand keypoints (fingertips and palm)
                # MediaPipe hand landmarks: https://google.github.io/mediapipe/solutions/hands.html
                # Index finger tip is landmark 8
                # Middle finger tip is landmark 12
                # Ring finger tip is landmark 16
                # Pinky tip is landmark 20
                # Thumb tip is landmark 4
                
                # Check if fingertips are near face region
                fingertips = [8, 12, 16, 20, 4]  # Index, middle, ring, pinky, thumb
                proximity_threshold = min(width, height) * 0.15  # 15% of image dimension
                
                for fingertip_idx in fingertips:
                    # Handle both old API (landmark object) and new API (list of landmarks)
                    if hasattr(hand_landmarks, 'landmark'):
                        # Old API
                        landmark = hand_landmarks.landmark[fingertip_idx]
                        x = int(landmark.x * width)
                        y = int(landmark.y * height)
                    elif isinstance(hand_landmarks, list) and len(hand_landmarks) > fingertip_idx:
                        # New API - landmarks is a list
                        landmark = hand_landmarks[fingertip_idx]
                        x = int(landmark.x * width)
                        y = int(landmark.y * height)
                    else:
                        # Can't access landmark, skip
                        continue
                        
                        # Check distance from face center
                        distance = np.sqrt(
                            (x - face_region['center_x'])**2 + 
                            (y - face_region['center_y'])**2
                        )
                        
                        # Also check if fingertip is within face bounding box
                        in_face_box = (
                            face_region['x_min'] - proximity_threshold <= x <= face_region['x_max'] + proximity_threshold and
                            face_region['y_min'] - proximity_threshold <= y <= face_region['y_max'] + proximity_threshold
                        )
                        
                        if in_face_box or distance < proximity_threshold:
                            # Hand is too close to face - likely inappropriate gesture
                            logging.warning(f"[image_validator] Detected hand/finger near face (distance: {distance:.1f}px)")
                            return True
                
                # Hands detected but not near face
                return False
                
        elif OPENCV_AVAILABLE:
            # Fallback: Use OpenCV for basic hand detection
            # OpenCV doesn't have built-in hand detection, so we'll use a simpler approach
            # Check for skin-colored regions near face
            # This is less accurate but better than nothing
            
            # Convert to HSV for skin detection
            hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
            
            # Define skin color range in HSV
            lower_skin = np.array([0, 20, 70], dtype=np.uint8)
            upper_skin = np.array([20, 255, 255], dtype=np.uint8)
            
            # Create mask for skin-colored pixels
            skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)
            
            # Find face region
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            
            if len(faces) == 0:
                return None
            
            x, y, w, h = faces[0]
            face_region_expanded = {
                'x_min': max(0, x - w),
                'x_max': min(img_array.shape[1], x + 2*w),
                'y_min': max(0, y - h),
                'y_max': min(img_array.shape[0], y + 2*h)
            }
            
            # Check if there's significant skin color near face (outside face region)
            # This is a heuristic - not as accurate as MediaPipe
            face_area = (face_region_expanded['x_max'] - face_region_expanded['x_min']) * \
                       (face_region_expanded['y_max'] - face_region_expanded['y_min'])
            
            # Count skin pixels in expanded face region
            skin_in_region = cv2.countNonZero(
                skin_mask[face_region_expanded['y_min']:face_region_expanded['y_max'],
                         face_region_expanded['x_min']:face_region_expanded['x_max']]
            )
            
            # If there's a lot of skin color near face (more than just the face itself), might be hands
            # This is a rough heuristic
            skin_ratio = skin_in_region / face_area if face_area > 0 else 0
            if skin_ratio > 0.8:  # Threshold - adjust as needed
                logging.warning(f"[image_validator] Detected possible hand near face (skin ratio: {skin_ratio:.2f})")
                return True
            
            return False
        else:
            # No hand detection available
            return None
            
    except Exception as e:
        logging.warning(f"[image_validator] Hand detection error: {e}")
        # On error, return None (can't determine)
        return None


def _check_hands_near_face_vision_api(image_path: str) -> Optional[bool]:
    """
    Fallback: Use OpenAI Vision API to check if hands/fingers are near the face.
    Returns True if hands detected near face, False if not, None if can't determine.
    """
    try:
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            return None  # Can't check without API key
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_api_key)
            
            # Read and prepare image
            img = Image.open(image_path)
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            # Resize if very large to reduce API costs
            max_size = 1024
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size), Image.LANCZOS)
            
            # Save to bytes buffer
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            buffer.seek(0)
            image_data = buffer.read()
            
            # Encode to base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            
            # Use OpenAI Vision API to check for hands/fingers near face
            model = os.getenv("MODEL_VISION", "gpt-4o-mini")
            
            hand_check_prompt = """Analyze this image and determine if the person has their hands, fingers, or any part of their hand near their face (touching face, picking nose, finger on chin, hand in mouth, etc.).

Respond with ONLY one word:
- "YES" if hands/fingers are clearly near or touching the face
- "NO" if hands are not near the face
- "UNCLEAR" if you cannot determine

Be strict - if there's any doubt, respond "YES"."""
            
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": hand_check_prompt
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_b64}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=10,
                    temperature=0.1
                )
                
                result_text = response.choices[0].message.content.strip().upper()
                
                if "YES" in result_text:
                    logging.warning(f"[image_validator] Vision API detected hands near face: {result_text}")
                    return True  # Hands detected near face
                elif "NO" in result_text:
                    return False  # No hands near face
                else:
                    # UNCLEAR or unexpected response
                    logging.warning(f"[image_validator] Vision API unclear response for hand detection: {result_text}")
                    return None  # Can't determine
                    
            except Exception as api_error:
                logging.error(f"[image_validator] OpenAI API error during hand detection: {api_error}")
                return None
                
        except ImportError:
            return None
            
    except Exception as e:
        logging.error(f"[image_validator] Vision API hand detection error: {e}")
        return None


def _check_content_safety(image_path: str) -> Tuple[bool, Optional[str]]:
    """Check content safety for nudity and inappropriate content using OpenAI Vision API."""
    try:
        # Try to use OpenAI Vision API for content moderation
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            # No API key - skip safety check
            logging.warning("[image_validator] OpenAI API key not available, skipping content safety check")
            return True, None
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_api_key)
            
            # Read and prepare image
            img = Image.open(image_path)
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            # Resize if very large to reduce API costs
            max_size = 1024
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size), Image.LANCZOS)
            
            # Save to bytes buffer
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            buffer.seek(0)
            image_data = buffer.read()
            
            # Encode to base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            
            # Use OpenAI Vision API to check for inappropriate content
            model = os.getenv("MODEL_VISION", "gpt-4o-mini")  # Use cheaper model for moderation
            
            moderation_prompt = """Analyze this image and determine if it contains:
1. Nudity or inappropriate exposure
2. Inappropriate gestures or poses
3. Any content not suitable for a children's book

Respond with ONLY one word: "SAFE" if the image is appropriate for children, or "UNSAFE" if it contains any inappropriate content.
Be strict - if there's any doubt, respond "UNSAFE"."""
            
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": moderation_prompt
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_b64}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=10,
                    temperature=0.1  # Low temperature for consistent moderation
                )
                
                result_text = response.choices[0].message.content.strip().upper()
                
                if "UNSAFE" in result_text or "INAPPROPRIATE" in result_text or "NOT SAFE" in result_text:
                    logging.warning(f"[image_validator] Content safety check failed: {result_text}")
                    return False, "Image content not appropriate for children's book"
                elif "SAFE" in result_text or "APPROPRIATE" in result_text:
                    return True, None
                else:
                    # Unexpected response - be cautious and reject
                    logging.warning(f"[image_validator] Unexpected moderation response: {result_text}")
                    return False, "Image content not appropriate for children's book"
                    
            except Exception as api_error:
                error_msg = str(api_error)
                # If it's a content policy violation, the image is definitely unsafe
                if "content_policy_violation" in error_msg.lower() or "safety" in error_msg.lower():
                    logging.warning(f"[image_validator] OpenAI flagged image as unsafe: {error_msg}")
                    return False, "Image content not appropriate for children's book"
                else:
                    # Other API errors - log but be lenient
                    logging.warning(f"[image_validator] OpenAI API error during moderation: {error_msg}")
                    return True, None
            
        except ImportError:
            logging.warning("[image_validator] OpenAI library not available")
            return True, None
        except Exception as e:
            logging.warning(f"[image_validator] Content safety check error: {e}")
            # On error, be lenient - don't block users
            return True, None
            
    except Exception as e:
        logging.error(f"[image_validator] Content safety check error: {e}")
        return True, None

