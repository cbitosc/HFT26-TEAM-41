import streamlit as st
import json
import os
from dotenv import load_dotenv
import base64
import io
import tempfile

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

from core_pipeline.main import run_full_pipeline
from core_pipeline.preprocessing import PADDLEX_AVAILABLE
from core_pipeline.preprocessing import fitz

st.set_page_config(page_title="Resume Parser", layout="wide")

st.title("📄 AI-Powered Resume Parser")
st.markdown("""
Upload a resume (PDF, Image) or paste text to extract structured information.
This tool leverages the Gemini API for robust parsing and PaddleX for image preprocessing.
""")


gemini_api_key = os.getenv("GEMINI_API_KEY")
if not gemini_api_key:
    st.warning("GEMINI_API_KEY not found in .env file. Please add it to run the parser.")
    gemini_api_key = st.text_input("Enter your Gemini API Key here:", type="password")

if not PADDLEX_AVAILABLE:
    st.warning("PaddleX is not fully installed or initialized. Image preprocessing will be skipped, and raw images will be sent to Gemini. Please check your PaddleX installation if you require preprocessing.")

if fitz is None:
    st.error("PyMuPDF (fitz) is not installed. PDF processing functionality will be unavailable.")


input_type = st.radio(
    "Select Input Type:",
    ("Upload PDF", "Upload Image", "Paste Text"),
    horizontal=True
)

uploaded_file = None
resume_text_input = ""
pdf_processing_mode = "image_based"

if input_type == "Upload PDF":
    uploaded_file = st.file_uploader("Upload PDF Resume", type=["pdf"])
    if fitz is not None:
        pdf_processing_mode = st.radio(
            "PDF Processing Mode:",
            ("Image-based (Send PDF pages as images to Gemini)", "Text-based (Extract text from PDF and send to Gemini)"),
            help="Image-based mode is generally more robust for complex layouts and works better for 2–3 page PDFs, but consumes more Gemini tokens. Text-based mode is faster and cheaper but may miss information from purely visual elements.",
            index=0
        )

        if "Image-based" in pdf_processing_mode:
            pdf_processing_mode = "image_based"
        else:
            pdf_processing_mode = "text_based"

elif input_type == "Upload Image":
    uploaded_file = st.file_uploader("Upload Image Resume", type=["png", "jpg", "jpeg"])
else:
    resume_text_input = st.text_area("Paste Resume Text Here", height=300)

if input_type == "Upload Image" or (input_type == "Upload PDF" and pdf_processing_mode == "image_based"):
    enable_preprocessing = st.checkbox("Enable Image Preprocessing for camera-taken images (Recommended for imperfect photos)", value=False)
    if not enable_preprocessing:
        st.info("Image preprocessing is disabled. Original image/PDF pages will be sent directly to Gemini.")
    elif not PADDLEX_AVAILABLE:
        st.warning("PaddleX is not available, so preprocessing cannot be performed even if enabled.")
else:
    enable_preprocessing = False


parsed_json_output = None
preprocessed_img_bytes_list = None

if st.button("Parse Resume", type="primary"):
    if not gemini_api_key:
        st.error("Please provide your Gemini API Key to proceed.")
    elif input_type == "Upload PDF" and uploaded_file and fitz is None:
        st.error("PyMuPDF (fitz) is required for PDF processing. Please install it.")
    else:
        with st.spinner("Parsing resume... This may take a moment."):
            if input_type == "Upload PDF" and uploaded_file:
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                    tmp_pdf.write(uploaded_file.getvalue())
                    temp_pdf_path = tmp_pdf.name
                
                parsed_json_output, preprocessed_img_bytes_list = run_full_pipeline(
                    api_key=gemini_api_key,
                    pdf_file_path=temp_pdf_path,
                    enable_preprocessing=enable_preprocessing,
                    pdf_processing_mode=pdf_processing_mode
                )
                os.unlink(temp_pdf_path)

            elif input_type == "Upload Image" and uploaded_file:

                image_bytes = uploaded_file.getvalue()
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                
                parsed_json_output, preprocessed_img_bytes_list = run_full_pipeline(
                    api_key=gemini_api_key,
                    image_data_base64=image_base64,
                    enable_preprocessing=enable_preprocessing
                )
            elif input_type == "Paste Text" and resume_text_input:
                parsed_json_output, preprocessed_img_bytes_list = run_full_pipeline(
                    api_key=gemini_api_key,
                    resume_text=resume_text_input,
                    enable_preprocessing=False,
                    pdf_processing_mode="text_based"
                )
            else:
                st.warning("Please upload a file or paste text to parse.")

if parsed_json_output:
    if "error" in parsed_json_output:
        st.error(f"Error parsing resume: {parsed_json_output['error']}")
        if 'full_response' in parsed_json_output:
            st.json(parsed_json_output['full_response']) # For debugging
    else:
        st.success("Resume parsed successfully! 🎉")
        
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Parsed JSON Output")
            st.json(parsed_json_output)

            json_string_for_download = json.dumps(parsed_json_output, indent=2)
            st.download_button(
                label="Download JSON",
                data=json_string_for_download,
                file_name="parsed_resume.json",
                mime="application/json"
            )
        
        with col2:
            # Only display images if the mode was image_based and images were generated
            if input_type == "Upload PDF" and pdf_processing_mode == "text_based":
                st.info("In 'Text-based' PDF mode, no images are generated for display.")
            elif preprocessed_img_bytes_list:
                st.subheader("Image View: Preprocessed / Original 🖼️")
                # Iterate and display each image
                for i, img_bytes in enumerate(preprocessed_img_bytes_list):
                    st.image(img_bytes, caption=f"Page {i+1}", use_container_width=True)
            elif input_type in ["Upload PDF", "Upload Image"]: # Only show info for file uploads
                if enable_preprocessing and PADDLEX_AVAILABLE:
                    st.info("No preprocessed images available for display (or PaddleX failed).")
                elif not enable_preprocessing:
                    st.info("Image preprocessing was disabled. Displaying original images is not supported here.")
                else:
                    st.info("PaddleX is not available, so preprocessing was skipped.")