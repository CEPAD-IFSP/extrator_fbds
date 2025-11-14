import pytesseract
from PIL import Image
import re
import os

def extract_year_and_datum(image_path):
    """Extract year from 'ANO XXXX' and datum from 'SIRGAS XXXX'"""
    
    # Open image
    img = Image.open(image_path)
    width, height = img.size
    
    # Crop bottom-right region
    right_bottom = img.crop((
        int(width * 0.65),
        int(height * 0.65),
        width,
        height
    ))
    
    # Perform OCR
    text = pytesseract.image_to_string(right_bottom, lang='por')
    
    # Remove extra whitespace and normalize
    text_normalized = ' '.join(text.split())
    
    # Pattern 1: ANO or ANO BASE followed by 4-digit year (flexible spacing, case-insensitive)
    # Matches: "ANO 2012", "ANO BASE 2012", "anoBase2012", etc.
    ano_match = re.search(r'(?i)ano(?:\s+base)?\s*(\d{4})', text_normalized)
    
    # Pattern 2: SIRGAS followed by 4-digit year (flexible spacing)
    # Matches: "SIRGAS 2000", "sirgas2000", "SiRgAs  2000", etc.
    sirgas_match = re.search(r'[Ss][Ii][Rr][Gg][Aa][Ss]\s*(\d{4})', text_normalized)
    
    results = {
        'ano': ano_match.group(1) if ano_match else None,
        'sirgas': sirgas_match.group(1) if sirgas_match else None,
        'raw_text': text  # Keep for debugging
    }
    
    return results