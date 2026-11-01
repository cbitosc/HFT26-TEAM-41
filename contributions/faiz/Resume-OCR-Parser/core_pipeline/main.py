import os
import tempfile
import shutil
from typing import Optional, Tuple, Dict, List
import base64
import io

from core_pipeline.preprocessing import (
    clear_directory,
    save_image_from_base64,
    run_doc_preprocessing,
    process_pdf_for_gemini,
    extract_text_and_links_from_pdf,
    PADDLEX_AVAILABLE
)
from core_pipeline.parser import parse_resume_with_gemini

def run_full_pipeline(
    api_key: str,
    resume_text: Optional[str] = None,
    image_data_base64: Optional[str] = None,
    pdf_file_path: Optional[str] = None,
    enable_preprocessing: bool = True,
    pdf_processing_mode: str = "image_based"
) -> Tuple[Dict, Optional[List[bytes]]]:
    """
    Runs the full resume parsing pipeline, including preprocessing and Gemini API call.

    Args:
        api_key: Your Gemini API key.
        resume_text: Raw text content of the resume.
        image_data_base64: Base64 encoded string of the resume image.
        pdf_file_path: Path to the PDF resume file.
        enable_preprocessing: Boolean flag to enable/disable image preprocessing.
        pdf_processing_mode: Specifies how PDF files should be processed:
                             "image_based" (renders PDF pages as images) or
                             "text_based" (extracts text from PDF).

    Returns:
        A tuple containing:
        - A dictionary with the structured resume data or an error message.
        - Optional list of bytes of the preprocessed image data (if applicable).
    """
    gemini_text_input = None
    gemini_image_parts: List[Dict[str, str]] = []
    extracted_pdf_links: List[Dict[str, str]] = []
    preprocessed_image_data_list: List[bytes] = []

    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        clear_directory(temp_dir)

        if pdf_file_path:
            if pdf_processing_mode == "image_based":
                # For PDF, extract hidden links and get preprocessed images
                pdf_processing_results = process_pdf_for_gemini(
                    pdf_file_path, temp_dir, enable_preprocessing and PADDLEX_AVAILABLE
                )
                extracted_pdf_links = pdf_processing_results.get("extracted_links", [])
                gemini_image_parts = pdf_processing_results.get("gemini_image_parts", [])
                
                # If there are processed images from PDF, decode all of them for display
                if gemini_image_parts:
                    for img_part in gemini_image_parts:
                        img_base64_data = img_part['inlineData']['data']
                        preprocessed_image_data_list.append(base64.b64decode(img_base64_data))
                print(f"PDF processed in image_based mode. Images sent to Gemini: {len(gemini_image_parts)}")

            elif pdf_processing_mode == "text_based":
                # For PDF, extract text and links
                pdf_text_results = extract_text_and_links_from_pdf(pdf_file_path)

                gemini_text_input = pdf_text_results.get("text", "")
                extracted_pdf_links = pdf_text_results.get("extracted_links", [])
                print("PDF processed in text_based mode. Text sent to Gemini.")
            else:
                return {"error": "Invalid PDF processing mode specified."}, None

        elif image_data_base64:
            input_img_path = os.path.join(temp_dir, "input_image.png")

            if not save_image_from_base64(image_data_base64, input_img_path):
                return {"error": "Failed to save input image for preprocessing."}, None

            final_image_base64 = image_data_base64
            current_image_bytes = base64.b64decode(image_data_base64)

            if enable_preprocessing and PADDLEX_AVAILABLE:
                processed_img_array = run_doc_preprocessing(input_img_path)

                if processed_img_array is not None:
                    try:
                        from PIL import Image
                        pil_image = Image.fromarray(processed_img_array)
                        byte_arr = io.BytesIO()
                        pil_image.save(byte_arr, format='PNG')
                        current_image_bytes = byte_arr.getvalue()
                        final_image_base64 = base64.b64encode(current_image_bytes).decode('utf-8')
                        print("Image preprocessed with PaddleX and added to Gemini input.")
                        
                    except ImportError:
                        print("Pillow not installed, cannot convert array to image bytes for display. Sending original.")

                    except Exception as e:
                        print(f"Error converting preprocessed array to image bytes: {e}. Sending original.")

                else:
                    print("PaddleX failed for image, sending original image to Gemini.")
            else:
                print("Image preprocessing disabled or PaddleX not available, sending original image to Gemini.")
            
            gemini_image_parts.append({
                "inlineData": {
                    "mimeType": "image/png",
                    "data": final_image_base64
                }
            })
            preprocessed_image_data_list.append(current_image_bytes)

        elif resume_text:
            gemini_text_input = resume_text

        else:
            return {"error": "No valid input (text, image, or PDF) provided for parsing."}, None

        # Call the Gemini parser
        parsed_data = parse_resume_with_gemini(
            api_key=api_key,
            text_input=gemini_text_input,
            image_parts=gemini_image_parts,
            extracted_pdf_links=extracted_pdf_links
        )
        return parsed_data, preprocessed_image_data_list

    except Exception as e:
        print(f"An error occurred in the full pipeline: {e}")
        return {"error": f"An error occurred during parsing: {e}"}, None
    
    finally:

        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"Cleaned up temporary directory: {temp_dir}")
            
if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Run Resume Parsing Pipeline")
    
    parser.add_argument("--api_key", type=str, required=True, help="Gemini API Key")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", type=str, help="Resume text input")
    group.add_argument("--image_path", type=str, help="Path to resume image (JPG, PNG)")
    group.add_argument("--pdf_path", type=str, help="Path to resume PDF file")

    parser.add_argument("--preprocess", action="store_true", help="Enable image preprocessing")
    parser.add_argument("--mode", choices=["image_based", "text_based"], default="image_based", help="PDF processing mode")

    args = parser.parse_args()

    # Handle image input
    image_base64 = None
    if args.image_path:
        with open(args.image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode('utf-8')

    parsed_output, _ = run_full_pipeline(
        api_key=args.api_key,
        resume_text=args.text,
        image_data_base64=image_base64,
        pdf_file_path=args.pdf_path,
        enable_preprocessing=args.preprocess,
        pdf_processing_mode=args.mode
    )

    print("\nParsed Output:")
    print(json.dumps(parsed_output, indent=2))
