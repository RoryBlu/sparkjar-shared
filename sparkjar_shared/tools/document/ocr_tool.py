"""
Image preprocessing tool for manuscript and document processing.
Optimizes images for LLM vision processing by resizing and encoding.

Handles large manuscript images by reducing size while preserving readability.
"""
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple, Type
from enum import Enum
import logging
from dataclasses import dataclass
from datetime import datetime
import hashlib
import base64

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, validator
import httpx

# Image preprocessing tool - no external OCR client needed
import json

logger = logging.getLogger(__name__)

    

class ImageFormat(str, Enum):
    """Supported image formats"""
    PNG = "png"
    JPEG = "jpeg"
    JPG = "jpg"
    BMP = "bmp"
    WEBP = "webp"
    
    @classmethod
    def from_extension(cls, ext: str) -> Optional["ImageFormat"]:
        """Get format from file extension"""
        ext = ext.lower().lstrip(".")
        for format in cls:
            if format.value == ext:
                return format
        return None

class OCRErrorType(str, Enum):
    """Types of OCR errors"""
    FILE_NOT_FOUND = "file_not_found"
    INVALID_FORMAT = "invalid_format"
    FILE_TOO_LARGE = "file_too_large"
    API_ERROR = "api_error"
    RATE_LIMIT = "rate_limit"
    PROCESSING_ERROR = "processing_error"
    VALIDATION_ERROR = "validation_error"

@dataclass
class ValidationResult:
    """Result of image validation"""
    is_valid: bool
    error_type: Optional[OCRErrorType] = None
    error_message: Optional[str] = None
    file_size_mb: Optional[float] = None
    image_format: Optional[ImageFormat] = None
    

class OCRError(Exception):
    """Base OCR error with context"""
    def __init__(self, error_type: OCRErrorType, message: str, details: Optional[Dict[str, Any]] = None):
        self.error_type = error_type
        self.message = message
        self.details = details or {}
        super().__init__(message)

class OCRToolInput(BaseModel):
    """Input schema for Image Preprocessing Tool"""
    image_path: str = Field(..., description="Path to the image file to process")
    max_size_kb: int = Field(
        default=500,
        description="Maximum size in KB for the output image (default: 500KB)"
    )
    enhance_contrast: bool = Field(
        default=True,
        description="Whether to enhance contrast for old/faded manuscripts (default: True)"
    )
    
    @validator("max_size_kb")
    def validate_size(cls, v):
        """Validate size is reasonable"""
        if v < 50:
            raise ValueError("Maximum size must be at least 50KB")
        if v > 2000:
            raise ValueError("Maximum size cannot exceed 2000KB")
        return v

class OCRTool(BaseTool):
    """
    Image preprocessing tool for optimizing manuscript images.
    
    Handles:
    - Image size reduction to meet API limits
    - Format conversion and optimization
    - Quality preservation for readability
    - Base64 encoding for LLM consumption
    """
    
    name: str = "image_optimizer"
    description: str = """Optimize manuscript images for AI vision processing.
    
    Takes a local image file path and returns the image as a data URL that agents can view.
    
    Features:
    - Enhances contrast for old/faded manuscripts
    - Reduces file size to stay under API limits
    - Sharpens text for better readability
    - Returns image as data URL (data:image/jpeg;base64,...)
    
    REQUIRED: Use this tool to convert file paths to viewable images before OCR."""
    
    args_schema: Type[BaseModel] = OCRToolInput
    
    # Configuration
    max_file_size_mb: float = Field(default=10.0, description="Maximum file size in MB")
    min_confidence_threshold: float = Field(default=0.3, description="Minimum confidence to accept")
    enable_caching: bool = Field(default=True, description="Cache results by image hash")
    api_timeout_seconds: int = Field(default=30, description="API timeout")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cache: Dict[str, OCRToolResult] = {}
        
    
    def _validate_image(self, image_path: str) -> ValidationResult:
        """
        Validate image before processing.
        
        Checks:
        - File exists
        - Correct format
        - Size limits
        """
        path = Path(image_path)
        
        # Check existence
        if not path.exists():
            return ValidationResult(
                is_valid=False,
                error_type=OCRErrorType.FILE_NOT_FOUND,
                error_message=f"Image file not found: {image_path}"
            )
        
        # Check format
        ext = path.suffix.lower().lstrip(".")
        image_format = ImageFormat.from_extension(ext)
        if image_format is None:
            return ValidationResult(
                is_valid=False,
                error_type=OCRErrorType.INVALID_FORMAT,
                error_message=f"Unsupported format: {ext}. Use PNG or JPEG."
            )
        
        # Check size
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > self.max_file_size_mb:
            return ValidationResult(
                is_valid=False,
                error_type=OCRErrorType.FILE_TOO_LARGE,
                error_message=f"File too large: {size_mb:.1f}MB (max: {self.max_file_size_mb}MB)"
            )
        
        return ValidationResult(
            is_valid=True,
            file_size_mb=size_mb,
            image_format=image_format
        )
    
    def _get_image_hash(self, image_path: str, cache_params: str) -> str:
        """Get hash of image for caching (includes cache parameters)"""
        with open(image_path, "rb") as f:
            content = f.read()
            # Include cache parameters in hash to differentiate different preprocessing options
            hash_input = f"{content}{cache_params}".encode()
            return hashlib.md5(hash_input).hexdigest()
    
    def _encode_image(self, image_path: str, max_size_kb: int = 500, enhance_contrast: bool = True) -> str:
        """Encode image to base64 with preprocessing for better OCR"""
        from PIL import Image, ImageEnhance, ImageFilter
        import io
        
        # Read the original image
        with Image.open(image_path) as img:
            # Convert RGBA to RGB if necessary
            if img.mode == 'RGBA':
                # Create a white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Apply contrast enhancement for manuscripts
            if enhance_contrast:
                # Enhance contrast
                contrast = ImageEnhance.Contrast(img)
                img = contrast.enhance(1.5)  # Increase contrast by 50%
                
                # Enhance sharpness for clearer text
                sharpness = ImageEnhance.Sharpness(img)
                img = sharpness.enhance(1.3)  # Increase sharpness by 30%
                
                # Apply slight denoise
                img = img.filter(ImageFilter.MedianFilter(size=1))
            
            # Check current size
            temp_buffer = io.BytesIO()
            img.save(temp_buffer, format='JPEG', quality=95)
            current_size_kb = len(temp_buffer.getvalue()) / 1024
            
            if current_size_kb <= max_size_kb:
                # Image is already small enough
                return base64.b64encode(temp_buffer.getvalue()).decode("utf-8")
            
            # Need to resize - try different quality levels first
            for quality in [85, 75, 65, 55, 45]:
                temp_buffer = io.BytesIO()
                img.save(temp_buffer, format='JPEG', quality=quality)
                current_size_kb = len(temp_buffer.getvalue()) / 1024
                
                if current_size_kb <= max_size_kb:
                    logger.info(f"Reduced image size to {current_size_kb:.1f}KB with quality {quality}")
                    return base64.b64encode(temp_buffer.getvalue()).decode("utf-8")
            
            # If quality reduction isn't enough, resize the image
            original_size = img.size
            scale = 1.0
            
            while current_size_kb > max_size_kb and scale > 0.1:
                scale *= 0.8  # Reduce by 20% each iteration
                new_size = (int(original_size[0] * scale), int(original_size[1] * scale))
                
                # Resize the image
                resized = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # Check size
                temp_buffer = io.BytesIO()
                resized.save(temp_buffer, format='JPEG', quality=85)
                current_size_kb = len(temp_buffer.getvalue()) / 1024
                
                if current_size_kb <= max_size_kb:
                    logger.info(f"Resized image from {original_size} to {new_size}, "
                              f"size: {current_size_kb:.1f}KB")
                    return base64.b64encode(temp_buffer.getvalue()).decode("utf-8")
            
            # Last resort - use very low quality
            temp_buffer = io.BytesIO()
            resized.save(temp_buffer, format='JPEG', quality=30)
            logger.warning(f"Had to use very low quality, final size: {len(temp_buffer.getvalue())/1024:.1f}KB")
            return base64.b64encode(temp_buffer.getvalue()).decode("utf-8")
    
    
    
    
    def _run(self, image_path: str, max_size_kb: int = 500, enhance_contrast: bool = False) -> str:
        """
        Preprocess an image for LLM vision processing.
        
        Args:
            image_path: Path to image file
            max_size_kb: Maximum output size in KB
            enhance_contrast: Whether to enhance contrast
            
        Returns:
            JSON string with preprocessed image data
        """
        start_time = datetime.now()
        
        try:
            # Validate image
            validation = self._validate_image(image_path)
            if not validation.is_valid:
                result = {
                    "success": False,
                    "image_path": image_path,
                    "error": validation.error_message
                }
                return json.dumps(result)
            
            # Check cache
            if self.enable_caching:
                cache_key = f"{image_path}_{max_size_kb}_{enhance_contrast}"
                image_hash = self._get_image_hash(image_path, cache_key)
                if image_hash in self._cache:
                    logger.info(f"Returning cached preprocessed image for {image_path}")
                    return self._cache[image_hash].json()
            
            # Encode and optimize image
            base64_image = self._encode_image(image_path, max_size_kb=max_size_kb, enhance_contrast=enhance_contrast)
            
            # Detect mime type
            image_prefix = base64_image[:20]
            if image_prefix.startswith("iVBOR"):
                mime_type = "image/png"
            else:
                mime_type = "image/jpeg"
            
            # Build result with base64 image data
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Return the image data URL directly for agent consumption
            result = {
                "success": True,
                "image_data_url": f"data:{mime_type};base64,{base64_image}",
                "original_path": image_path,
                "file_name": Path(image_path).name,
                "optimization_stats": {
                    "original_size_mb": round(validation.file_size_mb, 2),
                    "optimized_size_kb": round(len(base64_image) * 3 / 4 / 1024, 2),
                    "contrast_enhanced": enhance_contrast,
                    "processing_time_ms": processing_time
                }
            }
            
            # Cache result
            if self.enable_caching:
                self._cache[image_hash] = result
                
            return json.dumps(result)
            
        except Exception as e:
            logger.error(f"Failed to preprocess {image_path}: {str(e)}")
            result = {
                "success": False,
                "image_path": image_path,
                "error": str(e)
            }
            return json.dumps(result)
    
    def _enhanced_ocr(self, image_path: str, language: str = "es") -> str:
        """
        Enhanced OCR using gpt-4o for better accuracy on handwritten text.
        
        Args:
            image_path: Path to image file
            language: OCR language (default: "es" for Spanish)
            
        Returns:
            JSON string with OCR results in same format as _run()
        """
        start_time = datetime.now()
        
        try:
            # Validate image first
            validation = self._validate_image(image_path)
            if not validation.is_valid:
                result = {
                    "success": False,
                    "image_path": image_path,
                    "error": validation.error_message
                }
                return json.dumps(result)
            
            import openai
            client = openai.OpenAI()
            
            # Encode image for OpenAI
            base64_image = self._encode_image(image_path, max_size_kb=500)
            
            # Use gpt-4o for high quality OCR
            messages = [{
                "role": "system",
                "content": f"You are an expert at transcribing handwritten {language} text. Extract ALL text from the image exactly as written, preserving line breaks and formatting. Do not translate or interpret."
            }, {
                "role": "user",
                "content": [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]
            }]
            
            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=messages,
                max_tokens=1000
            )
            
            extracted_text = response.choices[0].message.content.strip()
            word_count = len(extracted_text.split())
            
            # Calculate processing time and build result
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            result = OCRToolResult(
                success=True,
                image_path=image_path,
                text=extracted_text,
                confidence=0.95,  # High confidence for gpt-4o
                word_count=word_count,
                language=language,
                processing_time_ms=processing_time,
                metadata={
                    "method": "enhanced_gpt4o",
                    "file_size_mb": validation.file_size_mb,
                    "format": validation.image_format.value,
                    "model": "gpt-4o"
                }
            )
            
            logger.info(f"Enhanced OCR completed: {word_count} words extracted")
            
            return result.json()
            
        except Exception as e:
            logger.error(f"Enhanced OCR failed for {image_path}: {str(e)}")
            result = OCRToolResult(
                success=False,
                image_path=image_path,
                language=language,
                error_type=OCRErrorType.PROCESSING_ERROR,
                error_message=f"Enhanced OCR failed: {str(e)}"
            )
            return result.json()
    
    def process_batch(self, image_paths: List[str], max_size_kb: int = 500) -> List[Dict[str, Any]]:
        """
        Process multiple images efficiently.
        
        Args:
            image_paths: List of image paths
            max_size_kb: Maximum size for each image
            
        Returns:
            List of preprocessing results
        """
        results = []
        
        for path in image_paths:
            result_json = self._run(path, max_size_kb=max_size_kb)
            result = json.loads(result_json)
            results.append(result)
            
        return results
    
    def clear_cache(self):
        """Clear the result cache"""
        self._cache.clear()
        logger.info("OCR cache cleared")
        
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "entries": len(self._cache),
            "size_estimate_mb": sum(len(r.json()) for r in self._cache.values()) / (1024 * 1024)
        }
    
