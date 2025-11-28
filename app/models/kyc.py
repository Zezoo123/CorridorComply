import base64
import io
from io import BytesIO
from typing import List, Optional, Tuple, Union
from pydantic import BaseModel, Field, field_validator, model_validator
from PIL import Image, UnidentifiedImageError
from .risk import RiskLevel


def decode_base64_image(image_data: str) -> Image.Image:
    """
    Decode a base64-encoded image string into a PIL Image.
    
    Args:
        image_data: Base64-encoded image string, optionally with data URL prefix
        
    Returns:
        PIL.Image.Image: The decoded image
        
    Raises:
        ValueError: If the image data is invalid or cannot be decoded
    """
    if not image_data:
        raise ValueError("Empty image data provided")
        
    # Remove data URL prefix if present
    if "," in image_data:
        image_data = image_data.split(",", 1)[1]
    
    try:
        # Add padding if needed
        padding = len(image_data) % 4
        if padding:
            image_data += "=" * (4 - padding)
            
        image_bytes = base64.b64decode(image_data)
        image = Image.open(BytesIO(image_bytes))
        return image.convert('RGB')  # Convert to RGB for consistency
        
    except (base64.binascii.Error, UnidentifiedImageError, Exception) as e:
        raise ValueError(f"Invalid image data: {str(e)}")

class KYCRequest(BaseModel):
    full_name: str = Field(..., example="Juan Dela Cruz")
    dob: str = Field(..., example="1990-01-01")  # later: use date type
    nationality: str = Field(..., example="PH")
    document_type: str = Field(..., example="passport")
    document_number: str = Field(..., example="P1234567")
    document_image_base64: Optional[str] = Field(
        None,
        example="data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBwgHBgkIBwgKCgkLDRYPDQwMDRsUFRAWIB0iIiAdHx8kKDQsJCYxJx8fLT0tMTU3Ojo6Iys/RD84QzQ5OjcBCgoKDQ0NGg8PGjclHyU3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3N//AABEIAIAAgAMBIgACEQEDEQH/xAAVAAEBAAAAAAAAAAAAAAAAAAAAB//EABQQAQAAAAAAAAAAAAAAAAAAAAD/2Q==",
        description="Base64-encoded document image (JPEG/PNG), with optional data URL prefix"
    )
    selfie_image_base64: Optional[str] = Field(
        None,
        example="data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBwgHBgkIBwgKCgkLDRYPDQwMDRsUFRAWIB0iIiAdHx8kKDQsJCYxJx8fLT0tMTU3Ojo6Iys/RD84QzQ5OjcBCgoKDQ0NGg8PGjclHyU3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3N//AABEIAIAAgAMBIgACEQEDEQH/xAAVAAEBAAAAAAAAAAAAAAAAAAAAB//EABQQAQAAAAAAAAAAAAAAAAAAAAD/2Q==",
        description="Base64-encoded selfie image (JPEG/PNG), with optional data URL prefix"
    )
    
    @model_validator(mode='after')
    def validate_images(self) -> 'KYCRequest':
        """Validate base64 image data if provided"""
        if self.document_image_base64:
            try:
                # Just validate, don't store the image in the model
                decode_base64_image(self.document_image_base64)
            except ValueError as e:
                raise ValueError(f"Invalid document image: {str(e)}")
                
        if self.selfie_image_base64:
            try:
                # Just validate, don't store the image in the model
                decode_base64_image(self.selfie_image_base64)
            except ValueError as e:
                raise ValueError(f"Invalid selfie image: {str(e)}")
                
        return self

class KYCResponse(BaseModel):
    request_id: str = Field(..., example="550e8400-e29b-41d4-a716-446655440000")
    status: str = Field(..., example="pass")  # "pass" | "fail" | "review"
    risk_score: int = Field(..., ge=0, le=100, example=15)
    risk_level: RiskLevel = RiskLevel.LOW
    details: List[str] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "status": "pass",
                "risk_score": 15,
                "risk_level": "low",
                "details": [
                    "Document format valid",
                    "Basic checks passed (stub)",
                ],
            }
        }
