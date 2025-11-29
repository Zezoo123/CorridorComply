# app/services/face_match.py
from typing import Tuple, Optional
from PIL import Image
import io
import numpy as np
from deepface import DeepFace
from deepface.commons import distance as dst
import logging

logger = logging.getLogger(__name__)

class FaceMatchingError(Exception):
    """Custom exception for face matching errors"""
    pass

class FaceMatchingService:
    """Service for comparing faces between document and selfie images"""
    
    # Similarity threshold (0-1), higher means more similar
    # This can be adjusted based on your security requirements
    SIMILARITY_THRESHOLD = 0.65  # 65% similarity threshold for a match
    
    @classmethod
    def compare_faces(
        cls, 
        document_image: Image.Image, 
        selfie_image: Image.Image
    ) -> Tuple[float, bool]:
        """
        Compare faces between document image and selfie image.
        
        Args:
            document_image: PIL Image containing the document photo
            selfie_image: PIL Image containing the selfie
            
        Returns:
            Tuple of (similarity_score, is_match)
            
        Raises:
            FaceMatchingError: If face detection fails or other errors occur
        """
        try:
            # Convert PIL Images to numpy arrays
            doc_img = np.array(document_image)
            selfie_img = np.array(selfie_image)
            
            # Verify faces are detected in both images
            try:
                doc_face = DeepFace.detectFace(doc_img, detector_backend='retinaface')
                selfie_face = DeepFace.detectFace(selfie_img, detector_backend='retinaface')
            except Exception as e:
                logger.error(f"Face detection failed: {str(e)}")
                raise FaceMatchingError("Could not detect face in one or both images")
                
            # Get face embeddings using Facenet (or other model)
            doc_embedding = DeepFace.represent(
                img_path=doc_img,
                model_name='Facenet',
                enforce_detection=False
            )
            
            selfie_embedding = DeepFace.represent(
                img_path=selfie_img,
                model_name='Facenet',
                enforce_detection=False
            )
            
            # Calculate cosine similarity between embeddings
            # Note: DeepFace uses cosine distance, so we subtract from 1 to get similarity
            distance = dst.findCosineDistance(doc_embedding, selfie_embedding)
            similarity = 1 - distance  # Convert distance to similarity score (0-1)
            
            # Determine if it's a match based on threshold
            is_match = similarity >= cls.SIMILARITY_THRESHOLD
            
            logger.info(f"Face comparison - Similarity: {similarity:.2f}, Match: {is_match}")
            return similarity, is_match
            
        except Exception as e:
            logger.error(f"Error in face matching: {str(e)}")
            raise FaceMatchingError(f"Face matching failed: {str(e)}")

    @classmethod
    def verify_faces(
        cls,
        document_image: Image.Image,
        selfie_image: Image.Image
    ) -> dict:
        """
        Verify if the faces in document and selfie match.
        
        Returns:
            dict: {
                "face_match_score": float,  # 0-1 similarity score
                "face_match_result": bool,  # True if faces match
                "error": Optional[str]      # Error message if any
            }
        """
        try:
            similarity, is_match = cls.compare_faces(document_image, selfie_image)
            return {
                "face_match_score": float(similarity),
                "face_match_result": is_match,
                "error": None
            }
        except FaceMatchingError as e:
            return {
                "face_match_score": 0.0,
                "face_match_result": False,
                "error": str(e)
            }