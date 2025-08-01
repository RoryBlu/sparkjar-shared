"""
NVIDIA NIM PaddleOCR client for optical character recognition.
"""
import base64
import os
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import httpx
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

class OCRBoundingBox(BaseModel):
    """Bounding box coordinates for detected text"""
    x: float
    y: float
    width: float
    height: float

class OCRTextResult(BaseModel):
    """Individual text detection result"""
    text: str = Field(..., description="Detected text content")
    confidence: float = Field(..., description="Confidence score (0-1)")
    bounding_box: Optional[OCRBoundingBox] = Field(None, description="Text location in image")
    

class OCRResponse(BaseModel):
    """Complete OCR response from PaddleOCR"""
    results: List[OCRTextResult] = Field(default_factory=list, description="All detected text segments")
    full_text: str = Field("", description="All text concatenated")
    raw_response: Optional[Dict[str, Any]] = Field(None, description="Raw API response")

class OCRClient:
    """Client for NVIDIA NIM PaddleOCR API"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OCR client.
        
        Args:
            api_key: NVIDIA NIM API key. If not provided, uses NVIDIA_NIM_API_KEY env var.
        """
        # REMOVED BY RORY - NVIDIA_NIM_API_KEY not used in this repo
        # self.api_key = api_key or os.getenv("NVIDIA_NIM_API_KEY")
        # if not self.api_key:
        #     raise ValueError("NVIDIA_NIM_API_KEY not found in environment or provided")
        # 
        # self.endpoint = os.getenv("NVIDIA_OCR_ENDPOINT", "https://ai.api.nvidia.com/v1/cv/baidu/paddleocr")
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("API key must be provided")
        self.endpoint = "https://ai.api.nvidia.com/v1/cv/baidu/paddleocr"
        self.client = httpx.Client(timeout=30.0)
        
    def _encode_image(self, image_source: Union[str, Path, bytes]) -> str:
        """
        Encode image to base64 string.
        
        Args:
            image_source: Path to image file, Path object, or raw bytes
            
        Returns:
            Base64 encoded image string
        """
        if isinstance(image_source, bytes):
            image_bytes = image_source
        else:
            image_path = Path(image_source)
            if not image_path.exists():
                raise FileNotFoundError(f"Image file not found: {image_path}")
            
            with open(image_path, "rb") as f:
                image_bytes = f.read()
        
        return base64.b64encode(image_bytes).decode("utf-8")
    
    def _prepare_payload(self, base64_image: str) -> Dict[str, Any]:
        """
        Prepare the API request payload.
        
        Args:
            base64_image: Base64 encoded image string
            
        Returns:
            Formatted payload for API request
        """
        # Detect image type from first few bytes
        image_prefix = base64_image[:20]
        if image_prefix.startswith("iVBOR"):
            mime_type = "image/png"
        elif image_prefix.startswith("/9j/"):
            mime_type = "image/jpeg"
        else:
            # Default to PNG if can't detect
            mime_type = "image/png"
            
        return {
            "input": [{
                "type": "image_url",
                "url": f"data:{mime_type};base64,{base64_image}"
            }]
        }
    
    def _parse_response(self, raw_response: Dict[str, Any]) -> OCRResponse:
        """
        Parse the API response into structured format.
        
        Args:
            raw_response: Raw JSON response from API
            
        Returns:
            Structured OCR response
        """
        results = []
        
        # The response structure may vary, handle common formats
        if "output" in raw_response:
            output = raw_response["output"]
            if isinstance(output, list):
                for item in output:
                    if isinstance(item, dict):
                        text = item.get("text", "")
                        confidence = item.get("confidence", 0.0)
                        
                        # Parse bounding box if available
                        bbox = None
                        if "bbox" in item:
                            bbox_data = item["bbox"]
                            if isinstance(bbox_data, dict):
                                bbox = OCRBoundingBox(
                                    x=bbox_data.get("x", 0),
                                    y=bbox_data.get("y", 0),
                                    width=bbox_data.get("width", 0),
                                    height=bbox_data.get("height", 0)
                                )
                        
                        results.append(OCRTextResult(
                            text=text,
                            confidence=confidence,
                            bounding_box=bbox
                        ))
        
        # Concatenate all text
        full_text = " ".join([r.text for r in results])
        
        return OCRResponse(
            results=results,
            full_text=full_text,
            raw_response=raw_response
        )
    
    async def ocr_async(self, image_source: Union[str, Path, bytes]) -> OCRResponse:
        """
        Perform OCR on an image asynchronously.
        
        Args:
            image_source: Path to image file, Path object, or raw bytes
            
        Returns:
            OCR results
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Encode image
                base64_image = self._encode_image(image_source)
                
                # Prepare request
                payload = self._prepare_payload(base64_image)
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "api-key": self.api_key
                }
                
                # Make request
                logger.info(f"Sending OCR request to {self.endpoint}")
                response = await client.post(
                    self.endpoint,
                    json=payload,
                    headers=headers
                )
                
                response.raise_for_status()
                raw_response = response.json()
                
                # Parse and return
                return self._parse_response(raw_response)
                
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error during OCR: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Error during OCR: {str(e)}")
                raise
    
    def ocr(self, image_source: Union[str, Path, bytes]) -> OCRResponse:
        """
        Perform OCR on an image synchronously.
        
        Args:
            image_source: Path to image file, Path object, or raw bytes
            
        Returns:
            OCR results
        """
        try:
            # Encode image
            base64_image = self._encode_image(image_source)
            
            # Prepare request
            payload = self._prepare_payload(base64_image)
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "api-key": self.api_key
            }
            
            # Make request
            logger.info(f"Sending OCR request to {self.endpoint}")
            response = self.client.post(
                self.endpoint,
                json=payload,
                headers=headers
            )
            
            response.raise_for_status()
            raw_response = response.json()
            
            # Parse and return
            return self._parse_response(raw_response)
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during OCR: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error during OCR: {str(e)}")
            raise
    
    def close(self):
        """Close the HTTP client"""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# Convenience functions
def ocr_image(image_source: Union[str, Path, bytes], api_key: Optional[str] = None) -> OCRResponse:
    """
    Perform OCR on an image using NVIDIA NIM PaddleOCR.
    
    Args:
        image_source: Path to image file, Path object, or raw bytes
        api_key: Optional API key (uses env var if not provided)
        
    Returns:
        OCR results
    """
    with OCRClient(api_key=api_key) as client:
        return client.ocr(image_source)

async def ocr_image_async(image_source: Union[str, Path, bytes], api_key: Optional[str] = None) -> OCRResponse:
    """
    Perform OCR on an image asynchronously using NVIDIA NIM PaddleOCR.
    
    Args:
        image_source: Path to image file, Path object, or raw bytes
        api_key: Optional API key (uses env var if not provided)
        
    Returns:
        OCR results
    """
    client = OCRClient(api_key=api_key)
    return await client.ocr_async(image_source)