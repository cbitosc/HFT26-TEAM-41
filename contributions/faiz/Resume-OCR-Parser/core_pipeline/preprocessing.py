# core_pipeline/preprocessing.py

import os
import shutil
import base64
import cv2
import numpy as np
from PIL import Image
from typing import List, Dict, Optional, Union
import io
import re

try:
    import fitz
except ImportError:
    fitz = None
    print("PyMuPDF (fitz) not installed. PDF processing functionality will be unavailable.")

try:
    from paddlex import create_pipeline
    
    try:
        paddle_x_pipeline = create_pipeline(pipeline="doc_preprocessor")
        PADDLEX_AVAILABLE = True
        print("PaddleX doc_preprocessor pipeline initialized successfully.")
        
    except Exception as e:
        paddle_x_pipeline = None
        PADDLEX_AVAILABLE = False
        print(f"Failed to initialize PaddleX pipeline: {e}. Image preprocessing with PaddleX will be skipped.")
        
except ImportError:
    paddle_x_pipeline = None
    PADDLEX_AVAILABLE = False
    print("PaddleX or its dependencies (numpy, opencv-python, PIL) not installed. Image preprocessing will be skipped.")

def clear_directory(directory_path: str):
    """Clears all files and subdirectories within a given directory."""
    if os.path.exists(directory_path):
        for filename in os.listdir(directory_path):
            file_path = os.path.join(directory_path, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}: {e}")
    else:
        os.makedirs(directory_path, exist_ok=True)

def save_image_from_base64(base64_string: str, save_path: str) -> Optional[str]:
    """Decodes base64 string and saves as an image file."""
    try:
        img_bytes = base64.b64decode(base64_string)
        with open(save_path, "wb") as f:
            f.write(img_bytes)
        return save_path
    except Exception as e:
        print(f"Error saving base64 image: {e}")
        return None

def run_doc_preprocessing(image_path: str) -> Optional[np.ndarray]:
    """Run PaddleX pipeline and return processed image as a numpy array."""
    if not PADDLEX_AVAILABLE or paddle_x_pipeline is None:
        print("PaddleX pipeline not available. Skipping preprocessing.")
        return None
    try:
        print(f"Running PaddleX doc_preprocessor on: {image_path}")
        results = list(paddle_x_pipeline.predict(
            input=image_path,
            use_doc_orientation_classify=True,
            use_doc_unwarping=True,
        ))
        if results and "output_img" in results[0]:
            return results[0]["output_img"]
        return None
    except Exception as e:
        print(f"Error running PaddleX preprocessing on {image_path}: {e}")
        return None

def normalize_url(text: str) -> str:
    """
    Normalize URLs or anchor text for comparison.
    """
    text = text.strip().lower()
    text = re.sub(r'^https?://(www\.)?', '', text)
    text = text.rstrip('/')
    return text

def extract_links_from_page(page) -> List[Dict[str, str]]:
    """
    Extract and return valid, non-self-referencing hyperlinks from a single PDF page.
    """
    extracted_links = []
    seen = set()

    words = page.get_text("words")

    for link in page.get_links():
        if link['kind'] != fitz.LINK_URI or 'uri' not in link:
            continue

        rect = fitz.Rect(link['from'])
        linked_words = [w[4] for w in words if fitz.Rect(w[:4]).intersects(rect)]

        anchor_text = " ".join(linked_words).strip()
        url = link['uri'].strip()

        norm_text = normalize_url(anchor_text)
        norm_url = normalize_url(url)

        if not anchor_text:
            continue
        if norm_text == norm_url:
            continue
        if len(anchor_text) < 2:
            continue
        if (anchor_text, url) in seen:
            continue

        extracted_links.append({"text": anchor_text, "url": url})
        seen.add((anchor_text, url))

    return extracted_links

def extract_text_and_links_from_pdf(pdf_path: str) -> Dict[str, Union[str, List[Dict[str, str]]]]:
    """
    Extracts full text and meaningful hyperlinks from a PDF.
    """
    full_text = []
    all_links: List[Dict[str, str]] = []

    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            full_text.append(page.get_text())
            links = extract_links_from_page(page)
            all_links.extend(links)
        doc.close()

        return {
            "text": "\n".join(full_text),
            "extracted_links": all_links
        }

    except Exception as e:
        print(f"Error extracting text and links from PDF: {e}")
        raise


def process_pdf_for_gemini(pdf_path: str, temp_dir: str, enable_preprocessing: bool) -> Dict[str, Union[List[Dict[str, str]], List[Dict[str, str]]]]:
    """
    Extracts hidden links from PDF and renders pages as preprocessed or original images for Gemini.
    Returns extracted links and list of base64 image data.
    """
    if fitz is None:
        raise ImportError("PyMuPDF (fitz) is not installed. Cannot process PDF files.")

    extracted_links: List[Dict[str, str]] = []
    gemini_image_parts: List[Dict[str, str]] = []
    
    try:
        doc = fitz.open(pdf_path)
        for page_num, page in enumerate(doc):

            extracted_links.extend(extract_links_from_page(page))

            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            
            img_np_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            
            if pix.n == 4: # RGBA
                img_np_array = cv2.cvtColor(img_np_array, cv2.COLOR_RGBA2RGB)
            elif pix.n == 1: # Grayscale
                img_np_array = cv2.cvtColor(img_np_array, cv2.COLOR_GRAY2RGB)

            final_image_base64 = None
            if enable_preprocessing and PADDLEX_AVAILABLE:
                input_img_path = os.path.join(temp_dir, f"page_{page_num+1}.png")
                Image.fromarray(img_np_array).save(input_img_path)

                processed_img_array = run_doc_preprocessing(input_img_path)
                
                if processed_img_array is not None:
                    # Convert processed array to bytes
                    pil_image = Image.fromarray(processed_img_array.astype(np.uint8))
                    byte_arr = io.BytesIO()
                    pil_image.save(byte_arr, format='PNG')
                    final_image_base64 = base64.b64encode(byte_arr.getvalue()).decode('utf-8')
                    print(f"Processed PDF page {page_num+1} with PaddleX and added to Gemini input.")
                else:
                    # Fallback to original image if PaddleX fails
                    pil_image = Image.fromarray(img_np_array)
                    byte_arr = io.BytesIO()
                    pil_image.save(byte_arr, format='PNG')
                    final_image_base64 = base64.b64encode(byte_arr.getvalue()).decode('utf-8')
                    print(f"PaddleX failed for PDF page {page_num+1}, sending original image to Gemini.")
                    
            else:
                # Preprocessing disabled or PaddleX not available, send original image
                pil_image = Image.fromarray(img_np_array)
                byte_arr = io.BytesIO()
                pil_image.save(byte_arr, format='PNG')
                final_image_base64 = base64.b64encode(byte_arr.getvalue()).decode('utf-8')
                print(f"PDF page {page_num+1} sent to Gemini without preprocessing (disabled or PaddleX unavailable).")
            
            if final_image_base64:
                gemini_image_parts.append({
                    "inlineData": {
                        "mimeType": "image/png",
                        "data": final_image_base64
                    }
                })

        doc.close()
        print("PDF images prepared for Gemini (text layer used only for explicit links).")
        return {"extracted_links": extracted_links, "gemini_image_parts": gemini_image_parts}
    except Exception as e:
        print(f"Error processing PDF: {e}")
        raise
    
if __name__ == "__main__":

    test_pdf_path = "path/to/pdf"  # Replace with an actual PDF path
    temp_dir = "temp_images"
    os.makedirs(temp_dir, exist_ok=True)

    result = process_pdf_for_gemini(
        pdf_path=test_pdf_path,
        temp_dir=temp_dir,
        enable_preprocessing=True
    )

    print("\n--- Extracted Links ---")
    for link in result['extracted_links']:
        print(link)

    print(f"\nTotal processed images: {len(result['gemini_image_parts'])}")

    for i, part in enumerate(result['gemini_image_parts'], 1):
        image_data = base64.b64decode(part["inlineData"]["data"])
        image = Image.open(io.BytesIO(image_data))
        output_path = os.path.join(temp_dir, f"final_output_page_{i}.png")
        image.save(output_path)
        print(f"Saved final output image: {output_path}")
