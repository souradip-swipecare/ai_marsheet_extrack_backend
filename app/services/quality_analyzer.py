import cv2
import numpy as np
from typing import Dict
from loguru import logger


class ImageQualityAnalyzer:
    """assess image quality to route between OCR and Vision API"""
    
    BLUR_THRESHOLD = 100.0
    CONTRAST_THRESHOLD = 35
    RESOLUTION_THRESHOLD = 800
    QUALITY_SCORE_FOR_OCR = 65
    
    def assess_quality(self, image_bytes: bytes) -> Dict:
        """
        analyze image quality and recommend processing path
        
        returns:
            quality_score: 0-100
            recommended_path: 'ocr' or 'vision'
            blur_score, contrast_score, resolution_score
        """
        try:
            img_array = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            if image is None:
                return self._poor_quality_result()
            
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            h, w = gray.shape
            
            blur_score = self._assess_blur(gray)
            contrast_score = self._assess_contrast(gray)
            resolution_score = self._assess_resolution(h, w)
            
            # weighted average - contrast matters most for OCR
            quality_score = (
                blur_score * 0.35 +
                contrast_score * 0.45 +
                resolution_score * 0.20
            )
            
            use_ocr = quality_score >= self.QUALITY_SCORE_FOR_OCR
            
            return {
                "quality_score": round(quality_score, 1),
                "blur_score": round(blur_score, 1),
                "contrast_score": round(contrast_score, 1),
                "resolution_score": round(resolution_score, 1),
                "recommended_path": "ocr" if use_ocr else "vision",
                "can_use_ocr": use_ocr,
                "image_size": (w, h)
            }
            
        except Exception as e:
            logger.error(f"Quality assessment failed: {e}")
            return self._poor_quality_result()
    
    def _assess_blur(self, gray: np.ndarray) -> float:
        """laplacian variance method for blur detection"""
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        if laplacian_var >= self.BLUR_THRESHOLD * 2:
            return 100.0
        elif laplacian_var >= self.BLUR_THRESHOLD:
            return 50.0 + ((laplacian_var - self.BLUR_THRESHOLD) / self.BLUR_THRESHOLD * 50)
        else:
            return max(0, (laplacian_var / self.BLUR_THRESHOLD) * 50)
    
    def _assess_contrast(self, gray: np.ndarray) -> float:
        """standard deviation for contrast"""
        std_dev = np.std(gray)
        
        if std_dev >= self.CONTRAST_THRESHOLD * 2:
            return 100.0
        else:
            return min(100, (std_dev / self.CONTRAST_THRESHOLD) * 50)
    
    def _assess_resolution(self, height: int, width: int) -> float:
        """check if resolution is adequate"""
        min_dim = min(height, width)
        
        if min_dim >= self.RESOLUTION_THRESHOLD * 2:
            return 100.0
        elif min_dim >= self.RESOLUTION_THRESHOLD:
            return 50.0 + ((min_dim - self.RESOLUTION_THRESHOLD) / self.RESOLUTION_THRESHOLD * 50)
        else:
            return max(0, (min_dim / self.RESOLUTION_THRESHOLD) * 50)
    
    def _poor_quality_result(self) -> Dict:
        return {
            "quality_score": 30.0,
            "blur_score": 30.0,
            "contrast_score": 30.0,
            "resolution_score": 30.0,
            "recommended_path": "vision",
            "can_use_ocr": False,
            "image_size": (0, 0)
        }


quality_analyzer = ImageQualityAnalyzer()
