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


def extract_text(self, file_content: bytes, filename: str) -> str:
    """Extract text from any file type (PDF or image)"""
    try:
        file_ext = filename.lower().split(".")[-1] if "." in filename else ""

        if file_ext == "pdf":
            # For PDFs, convert to images first, then OCR each page
            import fitz  # PyMuPDF

            pdf_doc = fitz.open(stream=file_content, filetype="pdf")
            text_parts = []

            for page_num in range(pdf_doc.page_count):
                page = pdf_doc[page_num]
                # Convert page to image (PNG bytes)
                pix = page.get_pixmap()
                img_data = pix.tobytes("png")

                # OCR the image using Google Vision
                page_text = self.extract_text_from_image(img_data)
                if page_text.strip():
                    text_parts.append(page_text)

            pdf_doc.close()
            return "\n".join(text_parts)
        else:
            # For images, use direct OCR
            return self.extract_text_from_image(file_content)

    except Exception as e:
        raise Exception(f"Error extracting text from {filename}: {str(e)}")
