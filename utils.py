import pdfkit
import os
import time
import secrets
from flask import render_template
from datetime import datetime

class InvoiceGenerator:
    def __init__(self, output_dir="static/invoices"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_invoice(self, order_id, user, items, total, shipping):
        # Generate Unique Invoice Number
        date_str = datetime.now().strftime("%Y%m%d")
        randid = secrets.token_hex(3).upper()
        invoice_num = f"INV-{date_str}-{user['id']}-{randid}"
        
        # Define output path
        filename = f"{invoice_num}.pdf"
        output_path = os.path.join(self.output_dir, filename)
        
        # HTML template (Create templates/invoice_template.html)
        html_content = render_template(
            "invoice_template.html",
            invoice_num=invoice_num,
            date=datetime.now().strftime("%d %b %Y"),
            user=user,
            items=items,
            total=total,
            shipping=shipping
        )
        
        # Generate PDF
        try:
            pdfkit.from_string(html_content, output_path)
        except Exception as e:
            print("PDF generation error: ", e)
            return invoice_num, None
            
        return invoice_num, f"invoices/{filename}"
