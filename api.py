import os
import random
import string
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
from flask import jsonify
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pymongo import MongoClient, ReturnDocument
import logging
import psutil

# Load environment variables
load_dotenv()

# ---------------- Logging Configuration ---------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ---------------- MongoDB Connection ---------------- #
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["savishkaara-aio"]
collection = db["event_registration"]

# Log database connection status
try:
    db.command("ping")
    logger.info("Connected to MongoDB successfully!")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")

# ---------------- Email & Server Configuration ---------------- #
DEFAULT_SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
DEFAULT_SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
DEFAULT_EMAIL_USER = os.getenv("EMAIL_USER")
DEFAULT_EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# ---------------- Directories Configuration ---------------- #
OUTPUT_FOLDER = "Qr_Generated"
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

TEMPLATES_FOLDER = "templates"
if not os.path.exists(TEMPLATES_FOLDER):
    os.makedirs(TEMPLATES_FOLDER)

# ---------------- Database Utility Functions ---------------- #

def generate_unique_ticket_number():
    """Generate a unique ticket number by checking the event_registration collection."""
    while True:
        ticket_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if not collection.find_one({"ticket_number": ticket_number}):
            return ticket_number

def save_ticket_in_db(ticket_number, ticket_details):
    """
    Save a new ticket document with creation timestamp and verified flag set to False.
    Document structure:
      - ticket_number (str)
      - timestamp (datetime)
      - ticket_details (dict)
      - verified (bool)
      - attendance_date_time (datetime or None)
    """
    document = {
        "ticket_number": ticket_number,
        "timestamp": datetime.now(),
        "ticket_details": ticket_details,
        "verified": False,
        "attendance_date_time": None
    }
    collection.insert_one(document)
    return document

def load_ticket_by_number(ticket_number):
    """Return the ticket document for a given ticket_number or None."""
    return collection.find_one({"ticket_number": ticket_number})

def update_ticket_in_db(ticket_number, additional_data=None):
    """
    Mark a ticket as verified and optionally update its ticket_details.
    Sets:
      - verified to True
      - attendance_date_time to current datetime
    Optionally, additional_data can update the ticket_details.
    Returns the updated document.
    """
    update_fields = {"verified": True, "attendance_date_time": datetime.now()}
    if additional_data and isinstance(additional_data, dict):
        update_fields["ticket_details"] = additional_data
    updated_doc = collection.find_one_and_update(
        {"ticket_number": ticket_number},
        {"$set": update_fields},
        return_document=ReturnDocument.AFTER
    )
    return updated_doc

# ---------------- Utility Functions for Image & Email ---------------- #

def download_template_image(url):
    """Download an image from a given URL and return a PIL Image object."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))
        return image
    except Exception as e:
        logger.error(f"Error downloading image: {e}")
        return None

def send_email_with_attachment(subject, recipient, body, attachment_path, sender_name,
                               email_format="plain", smtp_server=DEFAULT_SMTP_SERVER,
                               smtp_port=DEFAULT_SMTP_PORT, email_user=DEFAULT_EMAIL_USER,
                               email_password=DEFAULT_EMAIL_PASSWORD):
    """
    Send an email with an attachment.
    email_format: "plain" or "html".
    """
    try:
        message = MIMEMultipart()
        message['From'] = f"{sender_name} <{email_user}>"
        message['To'] = recipient
        message['Subject'] = subject
        message.attach(MIMEText(body, email_format))
        with open(attachment_path, "rb") as attachment:
            mime_base = MIMEBase('application', 'octet-stream')
            mime_base.set_payload(attachment.read())
            encoders.encode_base64(mime_base)
            mime_base.add_header('Content-Disposition', f'attachment; filename={os.path.basename(attachment_path)}')
            message.attach(mime_base)
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(email_user, email_password)
            server.send_message(message)
        status = f"Email sent to {recipient} with attachment {attachment_path}"
        logger.info(status)
        return status
    except Exception as e:
        error_msg = f"Failed to send email to {recipient}: {e}"
        logger.error(error_msg)
        return error_msg

def generate_ticket_qr(template_image, image_size=None, qr_config=None, ticket_details=None):
    """
    Generate a ticket image with an overlaid QR code.
    Returns: (ticket_number, output_path, ticket_details)
    """
    if image_size and "width" in image_size and "height" in image_size:
        template_image = template_image.resize((image_size["width"], image_size["height"]))
    ticket_number = generate_unique_ticket_number()
    if ticket_details is None:
        ticket_details = {}
    ticket_details["ticket_number"] = ticket_number

    qr_data_str = "\n".join(f"{key.upper()}: {value}" for key, value in ticket_details.items())
    default_qr_config = {"size": 150, "offset": {"x": 50, "y": 120}, "rotation": 0}
    if qr_config:
        default_qr_config.update(qr_config)
    qr_size = default_qr_config["size"]
    offset_x = default_qr_config["offset"].get("x", 50)
    offset_y = default_qr_config["offset"].get("y", 120)
    rotation = default_qr_config.get("rotation", 0)

    qr_obj = qrcode.QRCode(
        version=1,
        error_correction=ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr_obj.add_data(qr_data_str)
    qr_obj.make(fit=True)
    qr_image = qr_obj.make_image(fill_color="black", back_color="white").convert('RGB')
    qr_image = qr_image.resize((qr_size, qr_size))
    if rotation:
        qr_image = qr_image.rotate(rotation, expand=1)
    position = (
        template_image.width - qr_image.width - offset_x,
        template_image.height - qr_image.height - offset_y
    )
    template_image.paste(qr_image, position)
    event_name = ticket_details.get("event", "EVENT")
    roll_no = ticket_details.get("roll_no", "UNKNOWN")
    ticket_filename = f"{event_name}_{roll_no}_{ticket_number}.png"
    output_path = os.path.join(OUTPUT_FOLDER, ticket_filename)
    template_image.save(output_path)

    # Save the ticket in the database
    save_ticket_in_db(ticket_number, ticket_details)

    return ticket_number, output_path, ticket_details

# ---------------- Flask API Endpoints ---------------- #

app = Flask(__name__)

@app.route('/generated/<filename>')
def serve_generated_ticket(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)

@app.route('/generate_ticket', methods=['POST'])
def generate_ticket_endpoint():
    """
    POST /generate_ticket
    Expected JSON payload example (using a local template):
    {
      "email": "user@example.com",
      "use_image_url": false,
      "template_image_path": "sample_template.jpg",
      "image_size": {"width": 1240, "height": 480},
      "qr_config": {"size": 150, "offset": {"x": 1000, "y": 190}, "rotation": 0},
      "ticket_details": {
         "name": "John Doe",
         "roll_no": "12345",
         "event": "SampleEvent",
         "extra": "Additional info if needed"
      },
      "mail_credentials": {
         "email_user": "sender@example.com",
         "email_password": "password",
         "sender_name": "Admin"
      },
      "send_email": true,
      "email_subject": "Your Ticket for SampleEvent",
      "email_body": "<p>Dear John Doe,<br>Please find your ticket attached.</p>",
      "email_format": "html"
    }
    """
    data = request.get_json()
    if "email" not in data or not data["email"].strip():
        return jsonify({"error": "Missing required field: email"}), 400
    email = data["email"].strip()

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
        template_filename = data["template_image_path"]
        template_path = os.path.join(TEMPLATES_FOLDER, template_filename)
        if not os.path.exists(template_path):
            return jsonify({"error": f"Template image not found at {template_path}"}), 400
        template_image = Image.open(template_path)

    image_size = data.get("image_size")
    qr_config = data.get("qr_config")
    ticket_details = data.get("ticket_details", {})

    ticket_number, output_path, qr_data = generate_ticket_qr(
        template_image,
        image_size=image_size,
        qr_config=qr_config,
        ticket_details=ticket_details
    )

    mail_credentials = data.get("mail_credentials", {})
    email_user_cred = mail_credentials.get("email_user", DEFAULT_EMAIL_USER)
    email_password = mail_credentials.get("email_password", DEFAULT_EMAIL_PASSWORD)
    sender_name = mail_credentials.get("sender_name", "Admin")
    email_status = "Not sent"
    if data.get("send_email", False) and email_user_cred and email_password:
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
    ticket_url = url_for('serve_generated_ticket', filename=os.path.basename(output_path), _external=True)
    response = {
        "email": email,
        "email_status": email_status,
        "ticket_number": ticket_number,
        "ticket_url": ticket_url,
        "qr_data": qr_data
    }
    return jsonify(response), 200

@app.route('/verify_ticket', methods=['POST'])
def verify_ticket_endpoint():
    """
    POST /verify_ticket
    Expects a JSON payload:
    {
        "ticket_number": "TICKET123"
    }
    If the ticket is found and not yet verified, it is marked as verified and returns:
       "Ticket is verified."
    If already verified, returns:
       "Ticket already verified."
    """
    data = request.get_json()
    ticket_number = data.get("ticket_number", "").strip()
    if not ticket_number:
        return jsonify({"error": "Missing ticket_number field"}), 400

    ticket = load_ticket_by_number(ticket_number)
    if not ticket:
        return jsonify({"valid": False, "message": "Ticket not found."}), 404

    if ticket.get("verified", False):
        return jsonify({
            "valid": False,
            "message": "Ticket already verified.",
            "ticket_details": ticket["ticket_details"]
        }), 200
    else:
        updated_ticket = update_ticket_in_db(ticket_number)
        return jsonify({
            "valid": True,
            "message": "Ticket is verified.",
            "ticket_details": updated_ticket["ticket_details"]
        }), 200

@app.route('/update_ticket', methods=['POST'])
def update_ticket():
    """
    POST /update_ticket
    Expects a JSON payload:
    {
      "ticket_number": "TICKET123",
      "attendance_data": {
          "attended_at": "2024-01-01 10:00:00",
          "remarks": "Checked in at gate A"
      }
    }
    Updates the ticket details (merging additional attendance_data).
    """
    data = request.get_json()
    ticket_number = data.get("ticket_number", "").strip()
    if not ticket_number:
        return jsonify({"error": "Missing required field: ticket_number"}), 400

    attendance_data = data.get("attendance_data", {})
    updated_ticket = update_ticket_in_db(ticket_number, additional_data=attendance_data)
    if not updated_ticket:
        return jsonify({"error": "Ticket not found."}), 404
    elif not updated_ticket.get("verified", False):
        return jsonify({"error": "Failed to update the ticket."}), 500
    else:
        return jsonify({
            "message": "Ticket has been updated and marked as verified.",
            "ticket_details": updated_ticket["ticket_details"]
        }), 200

@app.route('/status', methods=['GET'])
def server_status():
    """
    GET /status
    Returns a JSON object with server status and the current timestamp.
    """
    return jsonify({
        "status": "Server is running.",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }), 200

# ---------------- Production Server Startup ---------------- #
if __name__ == "__main__":
    # Print a big banner on startup
    banner = r"""
 ________________________________________________________________
|                                                                |
|       EVENT REGISTRATION TICKET GENERATION API - PRODUCTION    |
|________________________________________________________________|
    """
    print(banner)
    logger.info("Starting Event Registration API...")

    # Check MongoDB connection status (already logged on connection above)
    try:
        db.command("ping")
        logger.info("MongoDB connection: SUCCESS")
    except Exception as e:
        logger.error(f"MongoDB connection: FAILED - {e}")

    # Start production WSGI server using Waitress
    from waitress import serve
    public_url = os.getenv("PUBLIC_URL", "http://0.0.0.0:3030")  # e.g., if using ngrok, set PUBLIC_URL env variable
    logger.info(f"Server starting at {public_url}")
    serve(app, host="0.0.0.0", port=3030)
