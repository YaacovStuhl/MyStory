"""
Storage utilities for user book storage.
Supports local file system and cloud storage (AWS S3, Google Cloud Storage, Cloudinary).
"""

import os
import logging
from datetime import datetime
from typing import Optional, Tuple
from PIL import Image

# Storage configuration
STORAGE_TYPE = os.getenv("STORAGE_TYPE", "local")  # local, s3, gcs, cloudinary
BASE_DIR = os.getcwd()
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
THUMBNAIL_DIR = os.path.join(BASE_DIR, "static", "thumbnails")

# Cloud storage configuration
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
GCS_BUCKET = os.getenv("GCS_BUCKET", "")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")


def get_user_storage_dir(user_id: int) -> str:
    """Get user-specific storage directory for local storage."""
    user_dir = os.path.join(OUTPUT_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    return user_dir


def generate_filename(user_id: int, story_id: str) -> Tuple[str, str]:
    """
    Generate filename in format: {user_id}_{timestamp}_{story_id}.pdf
    
    Returns:
        (filename, relative_path)
    """
    timestamp = int(datetime.utcnow().timestamp())
    filename = f"{user_id}_{timestamp}_{story_id}.pdf"
    
    if STORAGE_TYPE == "local":
        user_dir = get_user_storage_dir(user_id)
        relative_path = f"{user_id}/{filename}"
        full_path = os.path.join(user_dir, filename)
    else:
        # For cloud storage, use relative path
        relative_path = f"{user_id}/{filename}"
        full_path = relative_path
    
    return filename, relative_path


def generate_thumbnail_path(user_id: int, story_id: str, timestamp: int) -> Tuple[str, str]:
    """
    Generate thumbnail path.
    
    Returns:
        (filename, relative_path)
    """
    filename = f"{user_id}_{timestamp}_{story_id}_thumb.jpg"
    
    if STORAGE_TYPE == "local":
        os.makedirs(THUMBNAIL_DIR, exist_ok=True)
        user_thumb_dir = os.path.join(THUMBNAIL_DIR, str(user_id))
        os.makedirs(user_thumb_dir, exist_ok=True)
        relative_path = f"thumbnails/{user_id}/{filename}"
        full_path = os.path.join(user_thumb_dir, filename)
    else:
        relative_path = f"thumbnails/{user_id}/{filename}"
        full_path = relative_path
    
    return filename, relative_path


def create_thumbnail(pdf_path: str, thumbnail_path: str, size: Tuple[int, int] = (300, 300)) -> bool:
    """
    Create a thumbnail from the first page of the PDF.
    
    Args:
        pdf_path: Path to PDF file
        thumbnail_path: Path where thumbnail should be saved
        size: Thumbnail size (width, height)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        from pdf2image import convert_from_path
        
        # Convert first page of PDF to image
        images = convert_from_path(pdf_path, first_page=1, last_page=1, dpi=150)
        if not images:
            logging.warning(f"[storage] Failed to extract page from PDF: {pdf_path}")
            return False
        
        # Resize to thumbnail
        thumbnail = images[0].resize(size, Image.LANCZOS)
        
        # Save thumbnail
        os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
        thumbnail.save(thumbnail_path, "JPEG", quality=85)
        
        logging.info(f"[storage] Thumbnail created: {thumbnail_path}")
        return True
        
    except ImportError:
        logging.warning("[storage] pdf2image not installed. Install with: pip install pdf2image")
        logging.warning("[storage] Thumbnail generation disabled. Using first page image as fallback.")
        
        # Fallback: Use first page image if available
        try:
            # Try to use first preview image as thumbnail
            preview_dir = os.path.join(BASE_DIR, "static", "previews")
            # This is a simple fallback - in production, you'd want better logic
            return False
        except Exception as e:
            logging.error(f"[storage] Fallback thumbnail creation failed: {e}")
            return False
            
    except Exception as e:
        logging.error(f"[storage] Failed to create thumbnail: {e}")
        return False


def save_pdf_local(pdf_data: bytes, file_path: str) -> bool:
    """Save PDF to local file system."""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(pdf_data)
        logging.info(f"[storage] PDF saved locally: {file_path}")
        return True
    except Exception as e:
        logging.error(f"[storage] Failed to save PDF locally: {e}")
        return False


def save_pdf_s3(pdf_data: bytes, file_path: str) -> bool:
    """Save PDF to AWS S3."""
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )
        
        s3_client.put_object(
            Bucket=AWS_S3_BUCKET,
            Key=file_path,
            Body=pdf_data,
            ContentType='application/pdf'
        )
        
        logging.info(f"[storage] PDF saved to S3: {file_path}")
        return True
    except ImportError:
        logging.error("[storage] boto3 not installed. Install with: pip install boto3")
        return False
    except Exception as e:
        logging.error(f"[storage] Failed to save PDF to S3: {e}")
        return False


def save_pdf_gcs(pdf_data: bytes, file_path: str) -> bool:
    """Save PDF to Google Cloud Storage."""
    try:
        from google.cloud import storage
        
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(file_path)
        blob.upload_from_string(pdf_data, content_type='application/pdf')
        
        logging.info(f"[storage] PDF saved to GCS: {file_path}")
        return True
    except ImportError:
        logging.error("[storage] google-cloud-storage not installed. Install with: pip install google-cloud-storage")
        return False
    except Exception as e:
        logging.error(f"[storage] Failed to save PDF to GCS: {e}")
        return False


def save_pdf_cloudinary(pdf_data: bytes, file_path: str) -> bool:
    """Save PDF to Cloudinary."""
    try:
        import cloudinary
        import cloudinary.uploader
        
        cloudinary.config(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET
        )
        
        # Upload PDF
        result = cloudinary.uploader.upload(
            pdf_data,
            resource_type="raw",
            folder=os.path.dirname(file_path),
            public_id=os.path.basename(file_path).replace('.pdf', ''),
            format="pdf"
        )
        
        logging.info(f"[storage] PDF saved to Cloudinary: {result.get('secure_url')}")
        return True
    except ImportError:
        logging.error("[storage] cloudinary not installed. Install with: pip install cloudinary")
        return False
    except Exception as e:
        logging.error(f"[storage] Failed to save PDF to Cloudinary: {e}")
        return False


def save_pdf(pdf_data: bytes, file_path: str) -> bool:
    """
    Save PDF using configured storage type.
    
    Args:
        pdf_data: PDF file data as bytes
        file_path: Path where PDF should be saved (relative for cloud, absolute for local)
    
    Returns:
        True if successful, False otherwise
    """
    if STORAGE_TYPE == "local":
        # For local, file_path should be absolute
        if not os.path.isabs(file_path):
            file_path = os.path.join(OUTPUT_DIR, file_path)
        return save_pdf_local(pdf_data, file_path)
    elif STORAGE_TYPE == "s3":
        return save_pdf_s3(pdf_data, file_path)
    elif STORAGE_TYPE == "gcs":
        return save_pdf_gcs(pdf_data, file_path)
    elif STORAGE_TYPE == "cloudinary":
        return save_pdf_cloudinary(pdf_data, file_path)
    else:
        logging.error(f"[storage] Unknown storage type: {STORAGE_TYPE}")
        return False


def get_pdf_url(file_path: str) -> str:
    """
    Get URL to access PDF based on storage type.
    
    Args:
        file_path: Relative path to PDF
    
    Returns:
        URL to access the PDF
    """
    if STORAGE_TYPE == "local":
        # For local storage, return Flask URL
        from flask import url_for
        return url_for('static', filename=f'../outputs/{file_path}', _external=True)
    elif STORAGE_TYPE == "s3":
        return f"https://{AWS_S3_BUCKET}.s3.amazonaws.com/{file_path}"
    elif STORAGE_TYPE == "gcs":
        return f"https://storage.googleapis.com/{GCS_BUCKET}/{file_path}"
    elif STORAGE_TYPE == "cloudinary":
        # Would need to fetch from Cloudinary API
        return f"https://res.cloudinary.com/{CLOUDINARY_CLOUD_NAME}/raw/upload/{file_path}"
    else:
        return file_path


def get_thumbnail_url(thumbnail_path: str) -> str:
    """
    Get URL to access thumbnail based on storage type.
    
    Args:
        thumbnail_path: Relative path to thumbnail
    
    Returns:
        URL to access the thumbnail
    """
    if STORAGE_TYPE == "local":
        from flask import url_for
        return url_for('static', filename=thumbnail_path, _external=True)
    elif STORAGE_TYPE == "s3":
        return f"https://{AWS_S3_BUCKET}.s3.amazonaws.com/{thumbnail_path}"
    elif STORAGE_TYPE == "gcs":
        return f"https://storage.googleapis.com/{GCS_BUCKET}/{thumbnail_path}"
    elif STORAGE_TYPE == "cloudinary":
        return f"https://res.cloudinary.com/{CLOUDINARY_CLOUD_NAME}/image/upload/{thumbnail_path}"
    else:
        return thumbnail_path


def get_pdf_path(relative_path: str) -> str:
    """
    Get full path to PDF file based on storage type.
    
    Args:
        relative_path: Relative path to PDF (e.g., "user_id/filename.pdf")
    
    Returns:
        Full path to PDF file (absolute for local, relative for cloud)
    """
    if STORAGE_TYPE == "local":
        return os.path.join(OUTPUT_DIR, relative_path)
    else:
        return relative_path


def read_pdf(relative_path: str) -> Optional[bytes]:
    """
    Read PDF file from storage.
    
    Args:
        relative_path: Relative path to PDF
    
    Returns:
        PDF file data as bytes, or None if failed
    """
    try:
        if STORAGE_TYPE == "local":
            full_path = get_pdf_path(relative_path)
            if os.path.exists(full_path):
                with open(full_path, "rb") as f:
                    return f.read()
            else:
                logging.error(f"[storage] PDF file not found: {full_path}")
                return None
        elif STORAGE_TYPE == "s3":
            import boto3
            from botocore.exceptions import ClientError
            
            s3_client = boto3.client(
                's3',
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY
            )
            
            try:
                response = s3_client.get_object(Bucket=AWS_S3_BUCKET, Key=relative_path)
                return response['Body'].read()
            except ClientError as e:
                logging.error(f"[storage] Failed to read PDF from S3: {e}")
                return None
        elif STORAGE_TYPE == "gcs":
            from google.cloud import storage
            
            client = storage.Client()
            bucket = client.bucket(GCS_BUCKET)
            blob = bucket.blob(relative_path)
            return blob.download_as_bytes()
        elif STORAGE_TYPE == "cloudinary":
            import cloudinary
            import cloudinary.api
            
            cloudinary.config(
                cloud_name=CLOUDINARY_CLOUD_NAME,
                api_key=CLOUDINARY_API_KEY,
                api_secret=CLOUDINARY_API_SECRET
            )
            
            # Download from Cloudinary
            result = cloudinary.api.resource(relative_path, resource_type="raw")
            import requests
            response = requests.get(result['secure_url'])
            return response.content
        else:
            logging.error(f"[storage] Unknown storage type: {STORAGE_TYPE}")
            return None
    except Exception as e:
        logging.error(f"[storage] Failed to read PDF: {e}")
        return None


def delete_pdf(relative_path: str) -> bool:
    """
    Delete PDF file from storage.
    
    Args:
        relative_path: Relative path to PDF
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if STORAGE_TYPE == "local":
            full_path = get_pdf_path(relative_path)
            if os.path.exists(full_path):
                os.remove(full_path)
                logging.info(f"[storage] PDF deleted: {full_path}")
                return True
            else:
                logging.warning(f"[storage] PDF file not found for deletion: {full_path}")
                return False
        elif STORAGE_TYPE == "s3":
            import boto3
            from botocore.exceptions import ClientError
            
            s3_client = boto3.client(
                's3',
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY
            )
            
            try:
                s3_client.delete_object(Bucket=AWS_S3_BUCKET, Key=relative_path)
                logging.info(f"[storage] PDF deleted from S3: {relative_path}")
                return True
            except ClientError as e:
                logging.error(f"[storage] Failed to delete PDF from S3: {e}")
                return False
        elif STORAGE_TYPE == "gcs":
            from google.cloud import storage
            
            client = storage.Client()
            bucket = client.bucket(GCS_BUCKET)
            blob = bucket.blob(relative_path)
            blob.delete()
            logging.info(f"[storage] PDF deleted from GCS: {relative_path}")
            return True
        elif STORAGE_TYPE == "cloudinary":
            import cloudinary
            import cloudinary.uploader
            
            cloudinary.config(
                cloud_name=CLOUDINARY_CLOUD_NAME,
                api_key=CLOUDINARY_API_KEY,
                api_secret=CLOUDINARY_API_SECRET
            )
            
            # Delete from Cloudinary
            result = cloudinary.uploader.destroy(relative_path, resource_type="raw")
            if result.get('result') == 'ok':
                logging.info(f"[storage] PDF deleted from Cloudinary: {relative_path}")
                return True
            else:
                logging.error(f"[storage] Failed to delete PDF from Cloudinary: {result}")
                return False
        else:
            logging.error(f"[storage] Unknown storage type: {STORAGE_TYPE}")
            return False
    except Exception as e:
        logging.error(f"[storage] Failed to delete PDF: {e}")
        return False
