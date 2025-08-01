from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from fpdf import FPDF
import os
import re
from datetime import datetime
from typing import Type, Any

class PDFGeneratorSchema(BaseModel):
    """Input schema for PDF Generator Tool."""
    report: str = Field(..., description="The report content to convert to PDF")
    context: dict = Field(..., description="Context containing client_user_id and job_key")

class PDFGeneratorTool(BaseTool):
    """CrewAI Tool to convert reports to formatted PDFs."""
    
    name: str = "pdf_generator"
    description: str = "Convert the provided report (Markdown or text) into a formatted PDF and save to 'reports/' directory. Context must include 'client_user_id' and 'job_key'. Returns the PDF file path."
    args_schema: Type[BaseModel] = PDFGeneratorSchema

    def _run(self, report: str, context: dict) -> str:
        """
        CrewAI Tool: Convert the provided report (Markdown or text) into a formatted PDF
        and save to 'reports/' directory.
        Context must include 'client_user_id' and 'job_key'.
        Returns the PDF file path.
        """
        # Validate required context fields
        required_fields = ["client_user_id", "job_key"]
        for field in required_fields:
            if field not in context:
                raise ValueError(f"Missing required context field: {field}")
        
        # Extract identifiers
        user_id = context.get("client_user_id")
        job_key = context.get("job_key")

        # Construct output file path
        os.makedirs("reports", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"reports/{user_id}_{job_key}_{timestamp}.pdf"

        try:
            # Create PDF with better formatting
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_margins(20, 20, 20)
            
            # Title with timestamp
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, f"Report: {job_key}", ln=True, align='C')
            pdf.set_font("Arial", size=10)
            pdf.cell(0, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='C')
            pdf.ln(10)

            # Clean and process report content
            def clean_text_for_pdf(text):
                """Clean text to ensure compatibility with PDF generation."""
                # Replace smart quotes and other problematic Unicode characters
                replacements = {
                    '"': '"',  # Left double quotation mark
                    '"': '"',  # Right double quotation mark
                    ''': "'",  # Left single quotation mark
                    ''': "'",  # Right single quotation mark
                    '–': '-',  # En dash
                    '—': '-',  # Em dash
                    '…': '...',  # Horizontal ellipsis
                    '•': '*',  # Bullet point
                }
                
                for unicode_char, ascii_char in replacements.items():
                    text = text.replace(unicode_char, ascii_char)
                
                # Remove any remaining non-ASCII characters as fallback
                try:
                    # Test if the text can be encoded to latin-1 (FPDF's charset)
                    text.encode('latin-1')
                    return text
                except UnicodeEncodeError:
                    # Fallback: keep only ASCII characters
                    return text.encode('ascii', 'ignore').decode('ascii')

            pdf.set_font("Arial", size=11)
            lines = report.splitlines()
            
            for line in lines:
                line = line.strip()
                if not line:
                    pdf.ln(5)
                    continue
                
                # Clean the line for PDF compatibility
                line = clean_text_for_pdf(line)
                    
                # Handle basic markdown headers
                if line.startswith('# '):
                    pdf.set_font("Arial", 'B', 14)
                    pdf.cell(0, 8, line[2:], ln=True)
                    pdf.ln(3)
                    pdf.set_font("Arial", size=11)
                elif line.startswith('## '):
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 8, line[3:], ln=True)
                    pdf.ln(2)
                    pdf.set_font("Arial", size=11)
                elif line.startswith('### '):
                    pdf.set_font("Arial", 'B', 11)
                    pdf.cell(0, 8, line[4:], ln=True)
                    pdf.ln(1)
                    pdf.set_font("Arial", size=11)
                elif line.startswith('- ') or line.startswith('* '):
                    # Simple bullet point handling with dash
                    bullet_text = f"  - {line[2:]}"
                    pdf.cell(0, 6, bullet_text, ln=True)
                else:
                    # Regular text - now cleaned for PDF compatibility
                    pdf.cell(0, 6, line, ln=True)

            pdf.output(pdf_filename)
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate PDF: {e}")

        # Email functionality has been intentionally removed
        # PDF generation is complete without email notifications

        # PDF generated successfully
        return pdf_filename
