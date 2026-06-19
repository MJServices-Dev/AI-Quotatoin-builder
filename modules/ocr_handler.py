"""
OCR Handler Module
Handles Optical Character Recognition for scanned PDFs and images
"""

import os
from typing import Dict, List, Any, Optional
import PyPDF2


class OCRHandler:
    """Handle OCR processing for scanned documents and images"""
    
    def __init__(self, languages: List[str] = None):
        """
        Initialize OCR handler
        
        Args:
            languages: List of language codes (default: ['en'])
        """
        self.languages = languages or ['en']
        self.reader = None
        self._initialize_reader()
    
    def _initialize_reader(self):
        """Initialize EasyOCR reader lazily"""
        try:
            import easyocr
            self.reader = easyocr.Reader(self.languages, gpu=False)
        except Exception as e:
            print(f"Warning: Failed to initialize OCR reader: {e}")
            self.reader = None
    
    def is_scanned_pdf(self, pdf_path: str) -> bool:
        """
        Detect if a PDF is scanned (image-based) or text-based
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            True if PDF appears to be scanned
        """
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                # Check first few pages
                pages_to_check = min(3, len(pdf_reader.pages))
                
                for page_num in range(pages_to_check):
                    page = pdf_reader.pages[page_num]
                    text = page.extract_text()
                    
                    # If we get substantial text, it's not scanned
                    if text and len(text.strip()) > 100:
                        return False
                
                # If no substantial text found, likely scanned
                return True
                
        except Exception as e:
            print(f"Error checking if PDF is scanned: {e}")
            return False
    
    def preprocess_image(self, image: 'Any') -> 'Any':
        """
        Preprocess image for better OCR accuracy
        
        Args:
            image: Input image as numpy array
            
        Returns:
            Preprocessed image
        """
        import cv2
        import numpy as np
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray)
        
        # Increase contrast using CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast = clahe.apply(denoised)
        
        # Binarization using adaptive thresholding
        binary = cv2.adaptiveThreshold(
            contrast, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Deskew if needed
        coords = np.column_stack(np.where(binary > 0))
        if len(coords) > 0:
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle
            
            # Only deskew if angle is significant
            if abs(angle) > 0.5:
                (h, w) = binary.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                binary = cv2.warpAffine(
                    binary, M, (w, h),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE
                )
        
        return binary
    
    def extract_text_from_image(self, image_path: str, preprocess: bool = True) -> Dict[str, Any]:
        """
        Extract text from an image file using OCR
        
        Args:
            image_path: Path to image file
            preprocess: Whether to preprocess image
            
        Returns:
            Dictionary with extracted text and metadata
        """
        if not self.reader:
            return {
                'success': False,
                'error': 'OCR reader not initialized',
                'text': ''
            }
        
        try:
            import cv2
            import numpy as np
            # Read image
            image = cv2.imread(image_path)
            
            if image is None:
                return {
                    'success': False,
                    'error': 'Failed to read image',
                    'text': ''
                }
            
            # Preprocess if requested
            if preprocess:
                processed_image = self.preprocess_image(image)
            else:
                processed_image = image
            
            # Perform OCR
            results = self.reader.readtext(processed_image)
            
            # Extract text and confidence scores
            text_lines = []
            confidences = []
            
            for (bbox, text, confidence) in results:
                text_lines.append(text)
                confidences.append(confidence)
            
            # Combine text
            full_text = '\n'.join(text_lines)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return {
                'success': True,
                'text': full_text,
                'confidence': avg_confidence,
                'num_text_blocks': len(text_lines),
                'raw_results': results
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'text': ''
            }
    
    def extract_text_from_pdf(self, pdf_path: str, force_ocr: bool = False) -> Dict[str, Any]:
        """
        Extract text from PDF, using OCR if needed
        
        Args:
            pdf_path: Path to PDF file
            force_ocr: Force OCR even if text extraction works
            
        Returns:
            Dictionary with extracted text and metadata
        """
        try:
            # First try regular text extraction
            if not force_ocr:
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text_parts = []
                    
                    for page in pdf_reader.pages:
                        text = page.extract_text()
                        if text.strip():
                            text_parts.append(text.strip())
                    
                    # If we got substantial text, return it
                    full_text = '\n\n'.join(text_parts)
                    if len(full_text.strip()) > 50:
                        return {
                            'success': True,
                            'text': full_text,
                            'method': 'text_extraction',
                            'page_count': len(pdf_reader.pages)
                        }
            
            # If text extraction failed or forced OCR, use OCR
            if not self.reader:
                return {
                    'success': False,
                    'error': 'OCR reader not initialized and text extraction failed',
                    'text': ''
                }
            
            import numpy as np
            from pdf2image import convert_from_path
            
            # Convert PDF to images
            images = convert_from_path(pdf_path)
            
            all_text = []
            all_confidences = []
            
            for i, image in enumerate(images):
                # Convert PIL image to numpy array
                img_array = np.array(image)
                
                # Preprocess
                processed = self.preprocess_image(img_array)
                
                # OCR
                results = self.reader.readtext(processed)
                
                page_text = []
                page_confidences = []
                
                for (bbox, text, confidence) in results:
                    page_text.append(text)
                    page_confidences.append(confidence)
                
                if page_text:
                    all_text.append('\n'.join(page_text))
                    all_confidences.extend(page_confidences)
            
            full_text = '\n\n'.join(all_text)
            avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
            
            return {
                'success': True,
                'text': full_text,
                'method': 'ocr',
                'confidence': avg_confidence,
                'page_count': len(images)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'text': ''
            }
