from google.cloud import vision
import io
from PIL import Image
import os


class VisionService:
    def __init__(self):
        # Set credentials path
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = (
            "/opt/supercpe/google-credentials.json"  # ✅ Correct
        )
        self.client = vision.ImageAnnotatorClient()

    def extract_text_from_image(self, image_content: bytes) -> str:
        """Extract text from image using Google Cloud Vision"""
        try:
            # Create Vision API image object
            image = vision.Image(content=image_content)

            # Perform text detection
            response = self.client.text_detection(image=image)
            texts = response.text_annotations

            if texts:
                # Return the full text (first annotation contains all text)
                return texts[0].description
            else:
                return ""

        except Exception as e:
            raise Exception(f"Error extracting text from image: {str(e)}")

    def extract_text_from_pdf_image(self, pdf_page_image: Image.Image) -> str:
        """Convert PIL Image to bytes and extract text"""
        try:
            # Convert PIL Image to bytes
            img_byte_arr = io.BytesIO()
            pdf_page_image.save(img_byte_arr, format="PNG")
            img_byte_arr = img_byte_arr.getvalue()

            return self.extract_text_from_image(img_byte_arr)

        except Exception as e:
            raise Exception(f"Error processing PDF image: {str(e)}")
