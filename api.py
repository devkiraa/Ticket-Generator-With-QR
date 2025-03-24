import os
import csv
import random
import string
import time
import json
import requests
from datetime import datetime
from io import BytesIO
from flask import Flask, request, jsonify, send_from_directory, url_for
from PIL import Image
import qrcode
from qrcode.constants import ERROR_CORRECT_L
from dotenv import load_dotenv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Load environment variables
load_dotenv()

# Default email credentials (fallback if not provided in request payload)
DEFAULT_SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
DEFAULT_SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
DEFAULT_EMAIL_USER = os.getenv("EMAIL_USER")
DEFAULT_EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# Configure directories
OUTPUT_FOLDER = "Qr_Generated"
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

# CSV file for persisting ticket keys (to avoid duplicates)
KEY_FILE = "ticket_keys.csv"

# ---------------- Utility Functions ---------------- #

def generate_unique_ticket_number(existing_keys):
    """Generate a unique ticket number."""
    while True:
        ticket_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if ticket_number not in existing_keys:
            return ticket_number

def load_ticket_keys(key_file):
    """Load existing ticket keys from a CSV file."""
    ticket_keys = set()
    if os.path.exists(key_file):
        with open(key_file, mode="r") as file:
            reader = csv.reader(file)
            for row in reader:
                if row:
                    ticket_keys.add(row[0])
    return ticket_keys

def save_ticket_key(key_file, ticket_number):
    """Save a new ticket key to the CSV file with a timestamp."""
    with open(key_file, mode="a", newline="") as file:
        writer = csv.writer(file)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([ticket_number, timestamp])

def download_template_image(url):
    """Download an image from a given URL and return a PIL Image object."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))
        return image
    except Exception as e:
        print(f"Error downloading image: {e}")
        return None

def send_email_with_attachment(subject, recipient, body, attachment_path, sender_name,
                               email_format="plain", smtp_server=DEFAULT_SMTP_SERVER,
                               smtp_port=DEFAULT_SMTP_PORT, email_user=DEFAULT_EMAIL_USER,
                               email_password=DEFAULT_EMAIL_PASSWORD):
    """
    Send an email with an attachment.
    email_format: "plain" for text or "html" for HTML content.
    The sender name is included in the From header (e.g., "Admin <email@domain.com>").
    """
    try:
        message = MIMEMultipart()
        # Construct the From header with sender name and email address.
        message['From'] = f"{sender_name} <{email_user}>"
        message['To'] = recipient
        message['Subject'] = subject

        # Attach body (plain text or HTML)
        message.attach(MIMEText(body, email_format))

        # Open the file to be sent
        with open(attachment_path, "rb") as attachment:
            mime_base = MIMEBase('application', 'octet-stream')
            mime_base.set_payload(attachment.read())
            encoders.encode_base64(mime_base)
            mime_base.add_header('Content-Disposition', f'attachment; filename={os.path.basename(attachment_path)}')
            message.attach(mime_base)

        # Connect and send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(email_user, email_password)
            server.send_message(message)

        status = f"Email sent to {recipient} with attachment {attachment_path}"
        print(status)
        return status

    except Exception as e:
        error_msg = f"Failed to send email to {recipient}: {e}"
        print(error_msg)
        return error_msg

def generate_ticket_qr(template_image, image_size=None, qr_config=None, ticket_details=None, existing_keys=None):
    """
    Generate a ticket with a QR code overlaid.

    Parameters:
    - template_image: A PIL Image object (loaded template image).
    - image_size: dict with "width" and "height" to optionally resize template image.
    - qr_config: dict with keys:
         "size": int (size of QR code in pixels),
         "offset": dict with "x" and "y" (offset from bottom-right),
         "rotation": int (degrees to rotate the QR code).
    - ticket_details: dict with all details to be added to the QR data.
    - existing_keys: set of already generated ticket keys to ensure uniqueness.
    """
    if existing_keys is None:
        existing_keys = set()

    # Optionally resize the template image
    if image_size and "width" in image_size and "height" in image_size:
        template_image = template_image.resize((image_size["width"], image_size["height"]))

    # Generate a unique ticket number and add it to ticket_details
    ticket_number = generate_unique_ticket_number(existing_keys)
    if ticket_details is None:
        ticket_details = {}
    ticket_details["ticket_number"] = ticket_number

    # Build a multi-line string for QR code data using uppercase keys
    qr_data_str = "\n".join(f"{key.upper()}: {value}" for key, value in ticket_details.items())

    # Set default QR config if not provided
    default_qr_config = {"size": 150, "offset": {"x": 50, "y": 120}, "rotation": 0}
    if qr_config:
        default_qr_config.update(qr_config)
    qr_size = default_qr_config["size"]
    offset_x = default_qr_config["offset"].get("x", 50)
    offset_y = default_qr_config["offset"].get("y", 120)
    rotation = default_qr_config.get("rotation", 0)

    # Generate the QR code image
    qr = qrcode.QRCode(
        version=1,
        error_correction=ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data_str)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    qr_image = qr_image.resize((qr_size, qr_size))
    
    # Optionally rotate the QR image if needed
    if rotation:
        qr_image = qr_image.rotate(rotation, expand=1)

    # Determine QR placement position (placing at bottom-right with specified offset)
    position = (
        template_image.width - qr_image.width - offset_x,
        template_image.height - qr_image.height - offset_y
    )
    
    # Paste the QR code onto the template image
    template_image.paste(qr_image, position)
    
    # Build the ticket file name and save the image
    event_name = ticket_details.get("event", "EVENT")
    roll_no = ticket_details.get("roll_no", "UNKNOWN")
    ticket_filename = f"{event_name}_{roll_no}_{ticket_number}.png"
    output_path = os.path.join(OUTPUT_FOLDER, ticket_filename)
    template_image.save(output_path)
    
    # Save the ticket key for future uniqueness tracking
    save_ticket_key(KEY_FILE, ticket_number)
    
    # Also return the ticket details as a dict with lowercase keys for API response.
    qr_data_dict = {key.lower(): value for key, value in ticket_details.items()}
    
    return ticket_number, output_path, qr_data_dict

# ---------------- Flask API Application ---------------- #

app = Flask(__name__)

# Serve generated ticket images via an endpoint.
@app.route('/generated/<filename>')
def serve_generated_ticket(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)

@app.route('/generate_ticket', methods=['POST'])
def generate_ticket():
    """
    API endpoint to generate a ticket.

    Expected JSON payload example:
    {
      "email": "kirankichu6151@gmail.com",
      "use_image_url": true,
      "template_image_url": "https://www.eventim.sk/obj/media/AT-eventim/teaser/artworks/2024/twenty-one-pilots-2024-tickets-header.jpg",
      "image_size": {"width": 1240, "height": 480},
      "qr_config": {
        "size": 150,
        "offset": {"x": 1000, "y": 190},
        "rotation": 0
      },
      "ticket_details": {
         "name": "Kiran S",
         "roll_no": "KH.EN.U3CDS22042",
         "event": "SAVISHKAARA2K25",
         "extra": "Additional info if needed"
      },
      "mail_credentials": {
         "email_user": "mail.aeims@gmail.com",
         "email_password": "hbpduroqycmyzxld",
         "sender_name": "Admin"   // New field for sender name
      },
      "send_email": true,
      "email_subject": "Your Ticket for SAVISHKAARA2K25",
      "email_body": "<p>Dear John Doe,<br>Please find your ticket attached.<br>Enjoy the event!</p><div style=\"font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; background-color: #f8f8f8; border-radius: 10px; text-align: center;\"><h2 style=\"color: #fc8019; margin-bottom: 10px;\">Hey John Doe! 🎉</h2><p style=\"color: #333; font-size: 16px;\">Your ticket is ready! We've attached it to this email, so you're all set for an amazing experience.</p><p style=\"color: #666; font-size: 14px;\">Event: <strong>Your Event Name</strong> <br>Date & Time: <strong>DD/MM/YYYY, HH:MM AM/PM</strong> <br>Venue: <strong>Event Location</strong></p><p style=\"color: #333; font-size: 16px;\">Save your ticket, show it at the entry, and get ready for a fantastic time!</p><p style=\"font-size: 14px; color: #666;\">Need any help? We’ve got your back! <br>Reach out to our support team anytime.</p><a href=\"https://your-support-link.com\" style=\"display: inline-block; padding: 10px 20px; background-color: #fc8019; color: #fff; text-decoration: none; border-radius: 5px; font-size: 14px; margin-top: 10px;\">Contact Support</a><p style=\"font-size: 12px; color: #999; margin-top: 20px;\">Powered by <strong>Your Company Name</strong> 🚀</p></div>",
      "email_format": "html"
    }
    """
    data = request.get_json()

    # Only email is now required at the top level.
    if "email" not in data or not data["email"].strip():
        return jsonify({"error": "Missing required field: email"}), 400

    email = data["email"].strip()

    # Determine which template image to use
    use_image_url = data.get("use_image_url", False)
    template_image = None
    if use_image_url:
        if "template_image_url" not in data or not data["template_image_url"]:
            return jsonify({"error": "template_image_url must be provided when use_image_url is true"}), 400
        template_image = download_template_image(data["template_image_url"])
        if template_image is None:
            return jsonify({"error": "Failed to download template image from URL"}), 400
    else:
        if "template_image_path" not in data or not data["template_image_path"]:
            return jsonify({"error": "template_image_path must be provided when use_image_url is false"}), 400
        template_path = data["template_image_path"]
        if not os.path.exists(template_path):
            return jsonify({"error": f"Template image not found at {template_path}"}), 400
        template_image = Image.open(template_path)

    image_size = data.get("image_size")  # Optional dictionary with width and height
    qr_config = data.get("qr_config")    # Optional dict for QR code configuration

    # Get ticket_details from the request payload.
    ticket_details = data.get("ticket_details", {})

    # Load existing ticket keys to avoid duplicates
    existing_keys = load_ticket_keys(KEY_FILE)

    # Generate ticket with QR code overlay and obtain the updated ticket details as a dict.
    ticket_number, output_path, qr_data_dict = generate_ticket_qr(
        template_image,
        image_size=image_size,
        qr_config=qr_config,
        ticket_details=ticket_details,
        existing_keys=existing_keys
    )

    # Retrieve mail credentials from the request payload (if provided)
    mail_credentials = data.get("mail_credentials", {})
    email_user_cred = mail_credentials.get("email_user", DEFAULT_EMAIL_USER)
    email_password = mail_credentials.get("email_password", DEFAULT_EMAIL_PASSWORD)
    sender_name = mail_credentials.get("sender_name", "Admin")  # New sender name field

    # Optionally send the ticket via email if requested and credentials are available
    email_status = "Not sent"
    if data.get("send_email", False) and email_user_cred and email_password:
        # Email subject and body are taken directly from the request.
        email_subject = data.get("email_subject")
        email_body = data.get("email_body")
        email_format = data.get("email_format", "plain")
        email_status = send_email_with_attachment(
            email_subject,
            email,
            email_body,
            output_path,
            sender_name,
            email_format=email_format,
            smtp_server=DEFAULT_SMTP_SERVER,
            smtp_port=DEFAULT_SMTP_PORT,
            email_user=email_user_cred,
            email_password=email_password
        )

    # Construct a URL for the generated ticket (assuming the API is hosted appropriately)
    ticket_url = url_for('serve_generated_ticket', filename=os.path.basename(output_path), _external=True)

    response = {
        "email": email,
        "email_status": email_status,
        "qr_data": qr_data_dict,
        "ticket_number": ticket_number,
        "ticket_url": ticket_url
    }
    return jsonify(response), 200

# ---------------- Run the Flask App ---------------- #
if __name__ == "__main__":
    # For production, consider using a WSGI server like Gunicorn.
    app.run(host="0.0.0.0", port=5000, debug=True)
