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

# Folder for local templates
TEMPLATES_FOLDER = "templates"
if not os.path.exists(TEMPLATES_FOLDER):
    os.makedirs(TEMPLATES_FOLDER)

# CSV file for persisting ticket keys (to avoid duplicates)
KEY_FILE = "ticket_keys.csv"

# CSV file for attendance records
ATTENDANCE_FILE = "attendance.csv"

# ---------------- Utility Functions ---------------- #

def generate_unique_ticket_number(existing_keys):
    """Generate a unique ticket number."""
    while True:
        ticket_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if ticket_number not in existing_keys:
            return ticket_number

def load_ticket_keys_set(key_file):
    """Load just the ticket numbers from the CSV file."""
    ticket_keys = set()
    if os.path.exists(key_file):
        with open(key_file, mode="r", newline="") as file:
            reader = csv.reader(file)
            for row in reader:
                if row and len(row) >= 1:
                    ticket_keys.add(row[0])
    return ticket_keys

def save_ticket_key_with_details(key_file, ticket_number, ticket_details):
    """
    Save a new ticket key along with its details and a verified flag (default False).
    CSV columns: ticket_number, timestamp, ticket_details (JSON string), verified
    """
    with open(key_file, mode="a", newline="") as file:
        writer = csv.writer(file)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        details_json = json.dumps(ticket_details)
        writer.writerow([ticket_number, timestamp, details_json, "False"])

def load_all_ticket_keys(key_file):
    """
    Load all ticket records from the CSV file.
    Returns a list of dictionaries with keys: ticket_number, timestamp, ticket_details, verified.
    """
    records = []
    if os.path.exists(key_file):
        with open(key_file, mode="r", newline="") as file:
            reader = csv.reader(file)
            for row in reader:
                if row and len(row) >= 4:
                    try:
                        details = json.loads(row[2])
                    except Exception:
                        details = {}
                    record = {
                        "ticket_number": row[0],
                        "timestamp": row[1],
                        "ticket_details": details,
                        "verified": row[3].strip().lower() == "true"
                    }
                    records.append(record)
    return records

def update_ticket_record(key_file, ticket_number, additional_data=None):
    """
    Mark a ticket as verified (used) and optionally update ticket details with additional_data.
    Returns the updated record if found and updated, else None.
    """
    records = load_all_ticket_keys(key_file)
    updated_record = None
    for record in records:
        if record["ticket_number"] == ticket_number:
            if record["verified"]:
                updated_record = record
                break
            record["verified"] = True
            if additional_data and isinstance(additional_data, dict):
                record["ticket_details"].update(additional_data)
            updated_record = record
            break

    with open(key_file, mode="w", newline="") as file:
        writer = csv.writer(file)
        for rec in records:
            writer.writerow([
                rec["ticket_number"],
                rec["timestamp"],
                json.dumps(rec["ticket_details"]),
                "True" if rec["verified"] else "False"
            ])
    return updated_record

def record_attendance(record):
    """
    Append attendance information to the attendance CSV.
    Columns: ticket_number, verification timestamp, ticket details (as JSON).
    """
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(ATTENDANCE_FILE, "a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            record["ticket_number"],
            current_timestamp,
            json.dumps(record["ticket_details"])
        ])

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
      - template_image: A PIL Image object.
      - image_size: dict with "width" and "height" to optionally resize the template.
      - qr_config: dict with keys "size", "offset", "rotation".
      - ticket_details: dict with details to add to the QR code.
      - existing_keys: set of already generated ticket keys.
    """
    if existing_keys is None:
        existing_keys = set()
    if image_size and "width" in image_size and "height" in image_size:
        template_image = template_image.resize((image_size["width"], image_size["height"]))
    ticket_number = generate_unique_ticket_number(existing_keys)
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
    save_ticket_key_with_details(KEY_FILE, ticket_number, ticket_details)
    qr_data_dict = {key.lower(): value for key, value in ticket_details.items()}
    return ticket_number, output_path, qr_data_dict

# ---------------- Flask API Application ---------------- #

app = Flask(__name__)

@app.route('/generated/<filename>')
def serve_generated_ticket(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)

@app.route('/generate_ticket', methods=['POST'])
def generate_ticket():
    """
    API endpoint to generate a ticket.
    Expected JSON payload example:
    {
      "email": "user@example.com",
      "use_image_url": true,
      "template_image_url": "https://example.com/template.jpg",
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
        # If not using image URL, use a local template image from the TEMPLATES_FOLDER.
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
    existing_keys = load_ticket_keys_set(KEY_FILE)
    ticket_number, output_path, qr_data_dict = generate_ticket_qr(
        template_image,
        image_size=image_size,
        qr_config=qr_config,
        ticket_details=ticket_details,
        existing_keys=existing_keys
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
        "qr_data": qr_data_dict,
        "ticket_number": ticket_number,
        "ticket_url": ticket_url
    }
    return jsonify(response), 200

# ---------------- Updated Ticket Verification and Update Endpoints ---------------- #

@app.route('/verify_ticket', methods=['POST'])
def verify_ticket_endpoint():
    """
    POST endpoint to verify a ticket.
    Expects a JSON payload:
    {
        "ticket_number": "TICKET123"
    }
    If the ticket is found and not yet verified, it is marked as verified, records attendance, and returns:
       "Ticket is verified."
    If already verified, returns:
       "Ticket already verified."
    """
    data = request.get_json()
    ticket_number = data.get("ticket_number", "").strip()
    if not ticket_number:
        return jsonify({"error": "Missing ticket_number field"}), 400

    records = load_all_ticket_keys(KEY_FILE)
    for record in records:
        if record["ticket_number"] == ticket_number:
            if record["verified"]:
                return jsonify({
                    "valid": False,
                    "message": "Ticket already verified.",
                    "ticket_details": record["ticket_details"]
                }), 200
            else:
                updated_record = update_ticket_record(KEY_FILE, ticket_number)
                # Record attendance: write the ticket details along with current time to attendance CSV.
                record_attendance(updated_record)
                return jsonify({
                    "valid": True,
                    "message": "Ticket is verified.",
                    "ticket_details": updated_record["ticket_details"]
                }), 200
    return jsonify({"valid": False, "message": "Ticket not found."}), 404

@app.route('/update_ticket', methods=['POST'])
def update_ticket():
    """
    POST endpoint to update a ticket for marking attendance.
    Expects a JSON payload with:
    {
      "ticket_number": "TICKET123",
      "attendance_data": {
          "attended_at": "2024-01-01 10:00:00",
          "remarks": "Checked in at gate A"
      }
    }
    Marks the ticket as verified and updates its details.
    """
    data = request.get_json()
    ticket_number = data.get("ticket_number", "").strip()
    if not ticket_number:
        return jsonify({"error": "Missing required field: ticket_number"}), 400

    attendance_data = data.get("attendance_data", {})
    updated_record = update_ticket_record(KEY_FILE, ticket_number, additional_data=attendance_data)
    if updated_record is None:
        return jsonify({"error": "Ticket not found."}), 404
    elif not updated_record["verified"]:
        return jsonify({"error": "Failed to update the ticket."}), 500
    else:
        return jsonify({
            "message": "Ticket has been updated and marked as verified.",
            "ticket_details": updated_record["ticket_details"]
        }), 200

# ---------------- Server Status Endpoint ---------------- #

@app.route('/status', methods=['GET'])
def server_status():
    """
    GET endpoint to check server status.
    Returns a JSON with a message and the current timestamp.
    """
    return jsonify({
        "status": "Server is running.",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }), 200

# ---------------- Run the Flask App ---------------- #

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3030, debug=True)
