from PIL import Image
import os
import time
import csv
from tqdm import tqdm
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Email credentials
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

def send_email_with_attachment(subject, recipient, body, attachment_path):
    """Send an email with an attachment."""
    try:
        message = MIMEMultipart()
        message['From'] = EMAIL_USER
        message['To'] = recipient
        message['Subject'] = subject
        
        # Attach HTML body
        message.attach(MIMEText(body, 'html'))
        
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as attachment:
                mime_base = MIMEBase('application', 'octet-stream')
                mime_base.set_payload(attachment.read())
                encoders.encode_base64(mime_base)
                mime_base.add_header('Content-Disposition', f'attachment; filename={os.path.basename(attachment_path)}')
                message.attach(mime_base)
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(message)
        
        print(f"Email sent to {recipient} with attachment {attachment_path}")
    except Exception as e:
        print(f"Failed to send email to {recipient}: {e}")

def send_bulk_emails(csv_file, attachment_path):
    """Send emails to all recipients in the CSV file."""
    with open(csv_file, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in tqdm(reader, desc="Sending Emails"):
            name = row.get("name", "User")
            email = row.get("mail")
            if not email:
                print(f"Skipping invalid row: {row}")
                continue
            
            subject = "Payment Details for ESP32"
            body = f"""
            <html>
  <body>
    <p>Dear {name},</p>
    <p>We're excited to confirm your registration!</p>
    <p>To complete the payment for your ESP32, please find the UPI details below:</p>
    <p><b>UPI ID:</b> sidhumanojv@oksbi</p>
    <p><b>Payment Amount:</b> ₹300</p>
    <p>Please settle the payment by today, 4:30 PM, to avoid any registration issues.</p>
    <p>We've attached a payment QR image for your convenience.</p>
    <p>Thank you, and we look forward to your participation!</p>
    <p>After completing the payment, please upload the payment screenshot to the below form:</p>
    <p><a href="https://docs.google.com/forms/d/e/1FAIpQLSd3KjCDAylNXh9uMi419VNeePA5ul0gZPthM90MBXgAuGwi1Q/viewform?usp=dialog">Payment Screenshot Upload Form</a></p>
  </body>
</html>

            """
            send_email_with_attachment(subject, email, body, attachment_path)

def main():
    recipients_csv = "recipients.csv"
    attachment_path = "payment_qr.jpg"  # Change this to the actual ticket path
    send_bulk_emails(recipients_csv, attachment_path)

if __name__ == "__main__":
    main()