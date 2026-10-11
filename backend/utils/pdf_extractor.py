import io
import logging
from typing import Tuple
from pypdf import PdfReader
from fastapi import UploadFile, HTTPException

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB limit

def extract_text_from_pdf(file: UploadFile) -> Tuple[str, str]:
    """
    Validates and extracts text from an uploaded PDF file.
    Returns (extracted_text, filename).
    Raises HTTPException on validation or processing errors.
    """
    filename = file.filename or "resume.pdf"
    
    # 1. Extension validation
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Only PDF resumes (.pdf) are supported."
        )

    try:
        # Read content into memory
        contents = file.file.read()
        
        # 2. File size validation
        if len(contents) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds limit of 5MB. Uploaded size: {len(contents) / (1024 * 1024):.2f}MB"
            )
            
        if len(contents) < 50:
            raise HTTPException(
                status_code=400,
                detail="The uploaded PDF file is empty or corrupted."
            )

        # 3. PDF Parsing
        pdf_stream = io.BytesIO(contents)
        reader = PdfReader(pdf_stream)
        
        extracted_text_list = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                extracted_text_list.append(page_text)
                
        extracted_text = "\n".join(extracted_text_list).strip()
        
        if not extracted_text or len(extracted_text) < 20:
            raise HTTPException(
                status_code=400,
                detail="Could not extract readable text from the PDF. Please ensure your resume is not a scanned image PDF without searchable text."
            )

        logger.info(f"Successfully extracted {len(extracted_text)} characters from PDF: {filename}")
        return extracted_text, filename

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF extraction error for {filename}: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to process PDF file: {str(e)}"
        )
