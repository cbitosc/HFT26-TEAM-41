
# 📄 AI-Powered Resume Parser Pipeline

Welcome to the AI-Powered Resume Parser! This project provides a robust tool for extracting structured information from resumes in various formats (PDF, Image, or raw text) using the power of Google's Gemini API, with optional image preprocessing using PaddleX and hidden link detection.

## 📁 Directory Structure
```plaintext
.
core_pipeline
|
├── __init__.py
├── main.py                # Core pipeline logic (orchestrates preprocessing and parsing)
├── parser.py              # Handles interaction with Gemini API for parsing
├── preprocessing.py       # Manages image and PDF preprocessing (including PaddleX integration)
├── schema.py              # JSON response schema
└── README.md              # Documentation
```


## 🚀 Running the Pipeline

1. ✅ Make sure:
  - Dependencies from `requirements.txt` are installed.

2. ▶️ Run the pipeline:

#### For Text Input:
```bash
python -m core_pipeline.main --api_key "YOUR_KEY" --text "YOUR_RESUME_TEXT"
```

#### For Image Input:
```bash
python -m core_pipeline.main --api_key "YOUR_KEY" --image_path "/path/to/resume.png" --preprocess
```

#### For PDF Input (image-based):
```bash
python -m core_pipeline.main --api_key "YOUR_KEY" --pdf_path "/path/to/resume.pdf" --mode image_based --preprocess
```

#### For PDF Input (text-based):
```bash
python -m core_pipeline.main --api_key "YOUR_KEY" --pdf_path "/path/to/resume.pdf" --mode text_based
```


## 🙏 Acknowledgements

 - [PaddleX Preprocessing](https://paddlepaddle.github.io/PaddleX/latest/en/index.html#python-usage-doc-preprocessor)
 - [Gemini structured response](https://ai.google.dev/gemini-api/docs/structured-output)