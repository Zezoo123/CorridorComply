# app/services/face_match.py
from typing import Tuple, Optional, Dict, Any
from PIL import Image
import numpy as np
from deepface import DeepFace
from deepface.modules import verification, detection
import logging
import cv2

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
    def detect_faces(cls, image: np.ndarray) -> Dict[str, Any]:
        """
        Detect faces in an image and return face count and detection info.
        
        Args:
            image: Numpy array of the image
            
        Returns:
            dict: {
                'face_count': int,
                'face_locations': list,  # Bounding boxes of detected faces
                'error': Optional[str]   # Error message if any
            }
        """
        try:
            # Convert to RGB if it's BGR (OpenCV format)
            if image.shape[2] == 3:  # RGB
                rgb_image = image
            else:  # BGR to RGB
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Try with simpler parameters first (compatible with newer DeepFace versions)
            try:
                face_objs = detection.extract_faces(
                    img_path=rgb_image,
                    detector_backend='retinaface',
                    enforce_detection=False
                )
            except TypeError:
                # Fallback for older DeepFace versions that require target_size
                face_objs = detection.extract_faces(
                    img_path=rgb_image,
                    target_size=(160, 160),
                    detector_backend='retinaface',
                    enforce_detection=False
                )
            
            face_locations = []
            
            for face_obj in face_objs:
                if 'facial_area' in face_obj:
                    try:
                        # Handle different facial_area formats
                        if isinstance(face_obj['facial_area'], dict):
                            # If it's already a dictionary with x,y,w,h
                            x = face_obj['facial_area'].get('x', 0)
                            y = face_obj['facial_area'].get('y', 0)
                            w = face_obj['facial_area'].get('w', 0)
                            h = face_obj['facial_area'].get('h', 0)
                        else:
                            # If it's a tuple/list, handle different formats
                            area = face_obj['facial_area']
                            if len(area) == 4:  # x, y, w, h
                                x, y, w, h = area
                            else:  # x1, y1, x2, y2, ...
                                x, y, w, h = area[0], area[1], area[2] - area[0], area[3] - area[1]
                        
                        face_locations.append({
                            'x': int(x),
                            'y': int(y),
                            'width': int(w),
                            'height': int(h),
                            'confidence': float(face_obj.get('confidence', 1.0))
                        })
                    except Exception as e:
                        logger.warning(f"Could not process face detection: {str(e)}")
                        continue
            
            return {
                'face_count': len(face_locations),  # Use actual processed count
                'face_locations': face_locations,
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Face detection failed: {str(e)}")
            return {
                'face_count': 0,
                'face_locations': [],
                'error': f"Face detection failed: {str(e)}"
            }
    
    @classmethod
    def compare_faces(
        cls, 
        document_image: Image.Image, 
        selfie_image: Image.Image
    ) -> Dict[str, Any]:
        """
        Compare faces between document image and selfie image.
        
        Args:
            document_image: PIL Image containing the document photo
            selfie_image: PIL Image containing the selfie
            
        Returns:
            Dict containing comparison results and face detection info
        """
        try:
            # Convert PIL Images to numpy arrays
            doc_img = np.array(document_image)
            selfie_img = np.array(selfie_image)
            
            # Check face detection in both images first
            doc_faces = cls.detect_faces(doc_img)
            selfie_faces = cls.detect_faces(selfie_img)
            
            # Prepare result with detection info
            result = {
                'document_faces': doc_faces,
                'selfie_faces': selfie_faces,
                'face_match_score': 0.0,
                'face_match_result': False,
                'error': None
            }
            
            # Check for face detection errors
            if doc_faces['error']:
                raise FaceMatchingError(f"Document: {doc_faces['error']}")
            if selfie_faces['error']:
                raise FaceMatchingError(f"Selfie: {selfie_faces['error']}")
                
            # Check number of faces
            if doc_faces['face_count'] == 0:
                raise FaceMatchingError("No face detected in the document image")
            if selfie_faces['face_count'] == 0:
                raise FaceMatchingError("No face detected in the selfie")
            if doc_faces['face_count'] > 1:
                logger.warning(f"Multiple faces ({doc_faces['face_count']}) detected in document")
            if selfie_faces['face_count'] > 1:
                logger.warning(f"Multiple faces ({selfie_faces['face_count']}) detected in selfie")
            
            # If we got here, we have at least one face in each image
            try:
                # Using DeepFace's built-in verification
                verification_result = verification.verify(
                    img1_path=doc_img,
                    img2_path=selfie_img,
                    model_name='Facenet',
                    detector_backend='retinaface',
                    distance_metric='cosine',
                    enforce_detection=True
                )
                
                similarity = 1 - verification_result['distance']  # Convert distance to similarity score
                is_match = verification_result['verified']
                
                logger.info(f"Face comparison - Similarity: {similarity:.2f}, Match: {is_match}")
                
                result.update({
                    'face_match_score': float(similarity),
                    'face_match_result': is_match
                })
                
            except Exception as e:
                logger.error(f"Face verification failed: {str(e)}")
                raise FaceMatchingError(f"Face verification failed: {str(e)}")
                
            return result
            
        except Exception as e:
            logger.error(f"Error in face matching: {str(e)}")
            result = {
                'document_faces': doc_faces if 'doc_faces' in locals() else {'face_count': 0, 'error': 'Detection not attempted'},
                'selfie_faces': selfie_faces if 'selfie_faces' in locals() else {'face_count': 0, 'error': 'Detection not attempted'},
                'face_match_score': 0.0,
                'face_match_result': False,
                'error': str(e)
            }
            return result

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
                'face_match_score': float,  # 0-1 similarity score
                'face_match_result': bool,  # True if faces match
                'document_face_count': int, # Number of faces in document
                'selfie_face_count': int,   # Number of faces in selfie
                'error': Optional[str]      # Error message if any
            }
        """
        result = cls.compare_faces(document_image, selfie_image)
        
        return {
            'face_match_score': result['face_match_score'],
            'face_match_result': result['face_match_result'],
            'document_face_count': result['document_faces']['face_count'],
            'selfie_face_count': result['selfie_faces']['face_count'],
            'error': result.get('error')
        }