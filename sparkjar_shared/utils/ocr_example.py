"""
Example usage of OCR client in crew context.
"""
from typing import Dict, Any, List
from pathlib import Path
from utils.ocr_client import ocr_image
import logging

logger = logging.getLogger(__name__)

async def process_document_with_ocr(document_path: str) -> Dict[str, Any]:
    """
    Process a document image using OCR and return structured data.
    
    This can be used in a crew to extract text from images for further processing.
    
    Args:
        document_path: Path to the document image
        
    Returns:
        Dictionary with extracted text and metadata
    """
    try:
        # Perform OCR
        ocr_result = ocr_image(document_path)
        
        # Structure the results for crew processing
        extracted_data = {
            "status": "success",
            "document_path": document_path,
            "full_text": ocr_result.full_text,
            "segments": [],
            "metadata": {
                "total_segments": len(ocr_result.results),
                "average_confidence": 0.0
            }
        }
        
        # Process each text segment
        total_confidence = 0.0
        for result in ocr_result.results:
            segment = {
                "text": result.text,
                "confidence": result.confidence
            }
            
            # Add bounding box if available
            if result.bounding_box:
                segment["location"] = {
                    "x": result.bounding_box.x,
                    "y": result.bounding_box.y,
                    "width": result.bounding_box.width,
                    "height": result.bounding_box.height
                }
            
            extracted_data["segments"].append(segment)
            total_confidence += result.confidence
        
        # Calculate average confidence
        if ocr_result.results:
            extracted_data["metadata"]["average_confidence"] = total_confidence / len(ocr_result.results)
        
        logger.info(f"Successfully extracted text from {document_path}")
        return extracted_data
        
    except Exception as e:
        logger.error(f"Failed to process document {document_path}: {str(e)}")
        return {
            "status": "error",
            "document_path": document_path,
            "error": str(e)
        }

async def extract_text_from_multiple_images(image_paths: List[str]) -> List[Dict[str, Any]]:
    """
    Extract text from multiple images concurrently.
    
    Args:
        image_paths: List of paths to image files
        
    Returns:
        List of extraction results
    """
    import asyncio
    from .utils.ocr_client import ocr_image_async
    
    async def process_single_image(path: str) -> Dict[str, Any]:
        try:
            result = await ocr_image_async(path)
            return {
                "path": path,
                "status": "success",
                "text": result.full_text,
                "segments": len(result.results)
            }
        except Exception as e:
            return {
                "path": path,
                "status": "error",
                "error": str(e)
            }
    
    # Process all images concurrently
    tasks = [process_single_image(path) for path in image_paths]
    results = await asyncio.gather(*tasks)
    
    return results

# Example crew integration
class DocumentProcessingCrew:
    """
    Example crew that uses OCR for document processing.
    """
    
    async def process_invoice(self, invoice_image_path: str) -> Dict[str, Any]:
        """
        Process an invoice image to extract structured data.
        """
        # Step 1: OCR the invoice
        ocr_data = await process_document_with_ocr(invoice_image_path)
        
        if ocr_data["status"] != "success":
            return ocr_data
        
        # Step 2: Extract specific fields from the text
        full_text = ocr_data["full_text"]
        
        # Example field extraction (would be more sophisticated in practice)
        invoice_data = {
            "invoice_image": invoice_image_path,
            "raw_text": full_text,
            "extracted_fields": {
                "invoice_number": self._extract_invoice_number(full_text),
                "date": self._extract_date(full_text),
                "total_amount": self._extract_amount(full_text),
                "vendor": self._extract_vendor(full_text)
            },
            "confidence": ocr_data["metadata"]["average_confidence"]
        }
        
        return invoice_data
    
    def _extract_invoice_number(self, text: str) -> str:
        """Extract invoice number from text (simplified example)"""
        # In practice, use regex or NLP
        import re
        pattern = r"Invoice\s*#?\s*:?\s*(\w+)"
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1) if match else "Not found"
    
    def _extract_date(self, text: str) -> str:
        """Extract date from text (simplified example)"""
        import re
        # Simple date pattern - would be more comprehensive in practice
        pattern = r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
        match = re.search(pattern, text)
        return match.group(0) if match else "Not found"
    
    def _extract_amount(self, text: str) -> str:
        """Extract amount from text (simplified example)"""
        import re
        # Look for currency amounts
        pattern = r"\$[\d,]+\.?\d*"
        matches = re.findall(pattern, text)
        # Return the largest amount (likely the total)
        if matches:
            amounts = [float(m.replace("$", "").replace(",", "")) for m in matches]
            return f"${max(amounts):,.2f}"
        return "Not found"
    
    def _extract_vendor(self, text: str) -> str:
        """Extract vendor name (simplified - would use NER in practice)"""
        # In a real implementation, use NLP/NER to identify organization names
        lines = text.split("\n")
        # Often the vendor name is in the first few lines
        return lines[0] if lines else "Not found"