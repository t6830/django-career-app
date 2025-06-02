from io import BytesIO
from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams
import logging
import re

logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_file_obj):
    """
    Extracts plain text from a PDF file object.

    Args:
        pdf_file_obj: An open file-like object in binary mode.
                      The caller is responsible for opening and closing this object.
                      It's recommended to ensure pdf_file_obj.seek(0) if it might have been read.

    Returns:
        The extracted plain text as a string, or an empty string if extraction fails.
    """
    try:
        # Ensure the file pointer is at the beginning, especially if it was read before.
        # The caller should handle this if they pass a pre-read file object.
        # However, adding it here can prevent common issues.
        if hasattr(pdf_file_obj, 'seek') and callable(pdf_file_obj.seek):
            pdf_file_obj.seek(0)

        output_string_io = BytesIO()
        
        # laparams can be customized if needed, e.g., LAParams(line_margin=0.2)
        # codec is important for correct text decoding.
        extract_text_to_fp(
            pdf_file_obj, 
            output_string_io, 
            laparams=LAParams(), 
            output_type='text', 
            codec='utf-8' 
        )
        
        text = output_string_io.getvalue().decode('utf-8')
        output_string_io.close() # Good practice to close BytesIO object
        return text
    except Exception as e:
        # Log the error for debugging purposes
        logger.error(f"Error extracting text from PDF: {e}", exc_info=True)
        # Depending on requirements, could raise a custom exception here
        # e.g., raise PDFExtractionError("Failed to parse PDF content.")
        return ""

# Example of a custom exception (optional)
# class PDFExtractionError(Exception):
#     pass

def convert_pdf_to_markdown(pdf_file_obj):
    """
    Extracts text from a PDF file object and converts it to a basic Markdown format.

    Args:
        pdf_file_obj: An open file-like object in binary mode.

    Returns:
        The processed text as a Markdown-formatted string, or an empty string if extraction fails.
    """
    try:
        # Ensure the file pointer is at the beginning
        if hasattr(pdf_file_obj, 'seek') and callable(pdf_file_obj.seek):
            pdf_file_obj.seek(0)

        raw_text = extract_text_from_pdf(pdf_file_obj)
        if not raw_text:
            return ""

        lines = raw_text.splitlines()
        processed_lines = []
        for line in lines:
            stripped_line = line.strip()
            if stripped_line:  # Keep non-empty lines
                # Basic list item detection (could be more sophisticated)
                if re.match(r"^(?:[\*\-\+]|\d+\.)\s+", stripped_line):
                    processed_lines.append(stripped_line)  # Keep as is for now, let later stage handle paragraph breaks
                else:
                    processed_lines.append(stripped_line)
        
        # Join lines with single newlines, then handle paragraph breaks
        text_with_single_newlines = "\n".join(processed_lines)
        
        # Replace sequences of more than two newlines with exactly two newlines
        markdown_text = re.sub(r'\n{3,}', '\n\n', text_with_single_newlines)
        
        return markdown_text.strip()

    except Exception as e:
        logger.error(f"Error converting PDF to Markdown: {e}", exc_info=True)
        return ""
