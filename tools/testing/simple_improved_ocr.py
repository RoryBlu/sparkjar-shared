#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""Simple improved OCR without OpenCV dependencies."""
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

import json
import openai
from services.crew_api.src.tools.ocr_tool import OCRTool
from services.crew_api.src.tools.google_drive_tool import GoogleDriveTool
from PIL import Image, ImageEnhance, ImageFilter
import io
import base64

class SimpleImprovedOCR:
    """Improved OCR using PIL for preprocessing."""
    
    def __init__(self):
        self.ocr_tool = OCRTool()
        self.openai_client = openai.OpenAI()
    
    def preprocess_image_pil(self, image_path: str, method: str = "standard") -> str:
        """Apply preprocessing using PIL only."""
        img = Image.open(image_path)
        
        if method == "enhance_contrast":
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0)
            
        elif method == "sharpen":
            # Apply sharpening
            img = img.filter(ImageFilter.SHARPEN)
            
        elif method == "edge_enhance":
            # Enhance edges
            img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
            
        elif method == "brightness":
            # Adjust brightness
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(1.3)
            
        elif method == "combined":
            # Combination of enhancements
            # First contrast
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5)
            # Then sharpness
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(2.0)
        
        if method == "original":
            return image_path
        
        # Save processed image
        temp_path = f"/tmp/pil_processed_{method}_{Path(image_path).name}"
        img.save(temp_path)
        return temp_path
    
    def multi_pass_ocr(self, image_path: str) -> dict:
        """Perform multiple OCR passes with different preprocessing."""
        results = []
        
        # Different preprocessing methods
        methods = ["original", "enhance_contrast", "sharpen", "brightness", "combined"]
        
        for method in methods:
            logger.info(f"\nTrying method: {method}")
            
            # Preprocess image
            processed_path = self.preprocess_image_pil(image_path, method)
            
            # Run OCR
            result_json = self.ocr_tool._run(
                image_path=processed_path,
                language="es",  # Spanish
                detect_direction=False
            )
            
            result = json.loads(result_json)
            
            if result['success']:
                results.append({
                    'method': method,
                    'text': result.get('text', ''),
                    'words': result.get('word_count', 0),
                    'confidence': result.get('confidence', 0)
                })
                logger.info(f"  Words: {result.get('word_count', 0)}, Confidence: {result.get('confidence', 0):.2f}")
            
            # Clean up temp file
            if processed_path != image_path and Path(processed_path).exists():
                Path(processed_path).unlink()
        
        # Select best result
        if results:
            best = max(results, key=lambda x: x['words'] * max(x['confidence'], 0.5))
        else:
            best = {'method': 'none', 'text': '', 'words': 0, 'confidence': 0}
        
        return {
            'best_method': best['method'],
            'text': best['text'],
            'words': best['words'],
            'confidence': best['confidence'],
            'all_results': results
        }
    
    def post_process_with_llm(self, ocr_text: str, image_path: str) -> str:
        """Use LLM to improve OCR results."""
        if not ocr_text.strip():
            return ocr_text
            
        # Load and prepare image
        with Image.open(image_path) as img:
            # Resize for API
            max_dim = 2048
            if img.width > max_dim or img.height > max_dim:
                ratio = max_dim / max(img.width, img.height)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            buffer.seek(0)
            base64_image = base64.b64encode(buffer.read()).decode('utf-8')
        
        messages = [
            {
                "role": "system",
                "content": "You are an expert at improving OCR results from handwritten Spanish manuscripts. Fix errors and improve readability."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""OCR result from handwritten Spanish:

"{ocr_text}"

Correct OCR errors, fix word boundaries, add accents. Return ONLY corrected text."""
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ]
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return ocr_text

def main():
    """Process manuscripts with improved OCR."""
    logger.info("Simple Improved OCR Processing")
    logger.info("=" * 60)
    
    # Initialize
    ocr = SimpleImprovedOCR()
    drive_tool = GoogleDriveTool()
    
    # Get images
    client_user_id = "587f8370-825f-4f0c-8846-2e6d70782989"
    folder_path = "0AM0PEUhIEQFUUk9PVA/Vervelyn/Castor Gonzalez/book 1"
    
    result = drive_tool._run(
        folder_path=folder_path,
        client_user_id=client_user_id,
        download=True
    )
    
    data = json.loads(result)
    if data.get('status') != 'success':
        logger.error("Failed to get images")
        return
    
    files = data.get('files', [])[:3]  # First 3 pages
    
    # Process each page
    final_results = []
    
    for i, file in enumerate(files):
        logger.info(f"\n\nProcessing Page {i+1}: {file['name']}")
        logger.info("=" * 60)
        
        image_path = file.get('local_path')
        if image_path:
            # Multi-pass OCR
            ocr_result = ocr.multi_pass_ocr(image_path)
            
            logger.info(f"\nBest method: {ocr_result['best_method']}")
            logger.info(f"Words captured: {ocr_result['words']}")
            logger.info(f"Confidence: {ocr_result['confidence']:.2f}")
            
            # Post-process with LLM
            logger.info("\nImproving with LLM...")
            improved_text = ocr.post_process_with_llm(
                ocr_result['text'], 
                image_path
            )
            
            final_results.append({
                'page': i+1,
                'file': file['name'],
                'ocr_text': ocr_result['text'],
                'improved_text': improved_text,
                'ocr_words': ocr_result['words'],
                'improved_words': len(improved_text.split()) if improved_text else 0,
                'best_method': ocr_result['best_method'],
                'confidence': ocr_result['confidence']
            })
    
    # Save results
    output_file = "castor_simple_improved_final.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("CASTOR GONZALEZ - BOOK 1 - IMPROVED OCR RESULTS\n")
        f.write("=" * 60 + "\n\n")
        
        total_ocr_words = 0
        total_improved_words = 0
        
        for result in final_results:
            f.write(f"\nPAGE {result['page']}: {result['file']}\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"Best OCR Method: {result['best_method']}\n")
            f.write(f"OCR Confidence: {result['confidence']:.2f}\n\n")
            
            f.write("RAW OCR TEXT:\n")
            f.write("-" * 40 + "\n")
            f.write(result['ocr_text'] + "\n")
            f.write(f"Words: {result['ocr_words']}\n\n")
            
            f.write("IMPROVED TEXT:\n")
            f.write("-" * 40 + "\n")
            f.write(result['improved_text'] + "\n")
            f.write(f"Words: {result['improved_words']}\n")
            f.write("=" * 50 + "\n\n")
            
            total_ocr_words += result['ocr_words']
            total_improved_words += result['improved_words']
        
        f.write("\nSUMMARY:\n")
        f.write(f"Total OCR words: {total_ocr_words}\n")
        f.write(f"Total improved words: {total_improved_words}\n")
        if total_ocr_words > 0:
            f.write(f"Improvement: +{total_improved_words - total_ocr_words} words "
                    f"({(total_improved_words/total_ocr_words - 1)*100:.1f}% increase)\n")
    
    logger.info(f"\n\n✅ Improved OCR complete!")
    logger.info(f"Results saved to: {output_file}")
    
    # Upload to Google Drive
    logger.info("\nUploading to Google Drive...")
    upload_result = drive_tool._run(
        action="upload",
        file_path=output_file,
        folder_path=folder_path,
        client_user_id=client_user_id
    )
    logger.info(f"Upload: {json.loads(upload_result).get('status')}")
    
    drive_tool.cleanup()

if __name__ == "__main__":
    main()