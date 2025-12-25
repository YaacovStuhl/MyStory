"""
Enhanced logging module with file rotation and database logging.
Provides structured logging with context support.
"""

import os
import logging
import json
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict, Any

# Try to import database module
try:
    import database
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


class DatabaseLogHandler(logging.Handler):
    """Custom logging handler that writes to database."""
    
    def emit(self, record):
        """Emit a log record to database."""
        if not DB_AVAILABLE:
            return
        
        try:
            # Extract user_id from record if available
            user_id = getattr(record, 'user_id', None)
            
            # Get context from record if available
            context = getattr(record, 'context', {})
            
            # Build message with context
            message = record.getMessage()
            if context:
                message = f"{message} | Context: {json.dumps(context)}"
            
            # Add stack trace for errors
            if record.levelno >= logging.ERROR and record.exc_info:
                stack_trace = ''.join(traceback.format_exception(*record.exc_info))
                message = f"{message}\nStack Trace:\n{stack_trace}"
            
            # Write to database
            database.create_log(
                user_id=user_id,
                level=record.levelname,
                message=message
            )
        except Exception as e:
            # Don't let logging errors break the application
            print(f"[logger] Failed to write to database: {e}")


def setup_logging(log_dir: str = "logs", max_bytes: int = 10 * 1024 * 1024, backup_count: int = 5):
    """
    Setup comprehensive logging with file rotation and database logging.
    
    Args:
        log_dir: Directory for log files
        max_bytes: Maximum size of log file before rotation (default 10MB)
        backup_count: Number of backup files to keep
    """
    # Create log directory
    os.makedirs(log_dir, exist_ok=True)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    root_logger.handlers = []
    
    # Console handler with simple format
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter("[%(levelname)s] %(message)s")
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    log_file = os.path.join(log_dir, "app.log")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_format)
    root_logger.addHandler(file_handler)
    
    # Error log file (separate file for errors)
    error_log_file = os.path.join(log_dir, "errors.log")
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_format)
    root_logger.addHandler(error_handler)
    
    # Database handler
    if DB_AVAILABLE:
        db_handler = DatabaseLogHandler()
        db_handler.setLevel(logging.INFO)  # Only INFO and above to database
        root_logger.addHandler(db_handler)
    
    return root_logger


def log_user_login(user_id: int, oauth_provider: Optional[str] = None):
    """Log user login event."""
    logger = logging.getLogger("user")
    context = {
        "event": "user_login",
        "user_id": user_id,
        "oauth_provider": oauth_provider,
        "timestamp": datetime.utcnow().isoformat()
    }
    extra = {"user_id": user_id, "context": context}
    logger.info(f"User login: user_id={user_id}, oauth_provider={oauth_provider}", extra=extra)


def log_book_generation_start(user_id: Optional[int], story_id: str, child_name: str, job_id: str):
    """Log book generation start event."""
    logger = logging.getLogger("book")
    context = {
        "event": "book_generation_start",
        "user_id": user_id,
        "story_id": story_id,
        "child_name": child_name,
        "job_id": job_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    extra = {"user_id": user_id, "context": context}
    logger.info(
        f"Book generation started: user_id={user_id}, story_id={story_id}, child_name={child_name}, job_id={job_id}",
        extra=extra
    )


def log_image_generation(page_number: int, prompt_used: str, duration: float, status: str, job_id: str, error: Optional[str] = None):
    """Log image generation event."""
    logger = logging.getLogger("image")
    context = {
        "event": "image_generation",
        "page_number": page_number,
        "prompt_used": prompt_used[:200],  # Truncate long prompts
        "duration": duration,
        "status": status,
        "job_id": job_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    if error:
        context["error"] = error
    
    extra = {"context": context}
    level = logging.ERROR if status == "error" else logging.DEBUG
    message = f"Image generation: page={page_number}, status={status}, duration={duration:.2f}s, job_id={job_id}"
    if error:
        message += f", error={error}"
    logger.log(level, message, extra=extra)


def log_validation_failure(validation_type: str, reason: str, uploaded_filename: str, user_id: Optional[int] = None):
    """Log validation failure event."""
    logger = logging.getLogger("validation")
    context = {
        "event": "validation_failure",
        "validation_type": validation_type,
        "reason": reason,
        "uploaded_filename": uploaded_filename,
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    extra = {"user_id": user_id, "context": context}
    logger.warning(
        f"Validation failed: type={validation_type}, reason={reason}, filename={uploaded_filename}",
        extra=extra
    )


def log_api_error(api_name: str, error_message: str, stack_trace: Optional[str] = None, user_id: Optional[int] = None):
    """Log API error event."""
    logger = logging.getLogger("api")
    context = {
        "event": "api_error",
        "api_name": api_name,
        "error_message": error_message,
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    if stack_trace:
        context["stack_trace"] = stack_trace
    
    extra = {"user_id": user_id, "context": context}
    logger.error(
        f"API error: api={api_name}, error={error_message}",
        extra=extra,
        exc_info=stack_trace is not None
    )


def log_book_completed(book_id: int, total_duration: float, pdf_size: int, user_id: Optional[int] = None):
    """Log book completion event."""
    logger = logging.getLogger("book")
    context = {
        "event": "book_completed",
        "book_id": book_id,
        "total_duration": total_duration,
        "pdf_size": pdf_size,
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    extra = {"user_id": user_id, "context": context}
    logger.info(
        f"Book completed: book_id={book_id}, duration={total_duration:.2f}s, pdf_size={pdf_size} bytes",
        extra=extra
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)

