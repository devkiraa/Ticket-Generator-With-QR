import os
import csv
import random
import string
import time
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

# Email credentials (if you want to send the ticket by email as well)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

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


def send_email_with_attachment(subject, recipient, body, attachment_path):
    """Send an email with an attachment."""
    try:
        # Setup the MIME
        message = MIMEMultipart()
        message['From'] = EMAIL_USER
        message['To'] = recipient
        message['Subject'] = subject

        # Attach the body with the msg instance
        message.attach(MIMEText(body, 'plain'))

        # Open the file to be sent
        with open(attachment_path, "rb") as attachment:
            mime_base = MIMEBase('application', 'octet-stream')
            mime_base.set_payload(attachment.read())
            encoders.encode_base64(mime_base)
            mime_base.add_header('Content-Disposition', f'attachment; filename={os.path.basename(attachment_path)}')
            message.attach(mime_base)

        # Connect to the server and send the email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(message)

        print(f"Email sent to {recipient} with attachment {attachment_path}")

    except Exception as e:
        print(f"Failed to send email to {recipient}: {e}")


def generate_ticket_qr(
    name, roll_no, email,
    template_image, 
    image_size=None,
    qr_config=None,
    ticket_details=None,
    existing_keys=None
):
    """
    Generate a ticket with a QR code overlaid.
    
    Parameters:
    - name, roll_no, email: Ticket owner details.
    - template_image: A PIL Image object (loaded template image).
    - image_size: dict with "width" and "height" to optionally resize template image.
    - qr_config: dict with keys:
         "size": int (size of qr code in pixels),
         "offset": dict with "x" and "y" (offset from bottom-right),
         "rotation": int (degrees to rotate the QR code).
    - ticket_details: dict with extra details to be added to the QR data.
    - existing_keys: set of already generated ticket keys to ensure uniqueness.
    """
    if existing_keys is None:
        existing_keys = set()

    # Optionally resize the template image
    if image_size and "width" in image_size and "height" in image_size:
        template_image = template_image.resize((image_size["width"], image_size["height"]))

    # Generate a unique ticket number
    ticket_number = generate_unique_ticket_number(existing_keys)
    
    # Construct QR data. You can add additional details as needed.
    extra_info = " | ".join(f"{k.upper()}: {v}" for k, v in ticket_details.items()) if ticket_details else ""
    qr_data = f"NAME: {name}, ROLL-NO: {roll_no}, EMAIL: {email}, Ticket Number: {ticket_number} {extra_info}"
    
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
    qr.add_data(qr_data)
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
    ticket_filename = f"{ticket_details.get('event', 'EVENT')}_{roll_no}_{ticket_number}.png" if ticket_details else f"TICKET_{roll_no}_{ticket_number}.png"
    output_path = os.path.join(OUTPUT_FOLDER, ticket_filename)
    template_image.save(output_path)
    
    # Save the ticket key for future uniqueness tracking
    save_ticket_key(KEY_FILE, ticket_number)
    
    return ticket_number, output_path, qr_data


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
        "name": "John Doe",
        "roll_no": "12345",
        "email": "john@example.com",
        "template_image_url": "https://example.com/template.png",
        "template_image_path": "Template/mytemplate.png",  // Optional if not using URL
        "image_size": {"width": 800, "height": 600},          // Optional
        "qr_config": {
            "size": 150,
            "offset": {"x": 50, "y": 120},
            "rotation": 0
        },
        "ticket_details": {
            "event": "SAVISHKAARA2K25",
            "extra": "Additional info if needed"
        },
        "send_email": false  // Optional flag to trigger email sending
    }
    """
    data = request.get_json()
    required_fields = ["name", "roll_no", "email"]
    missing_fields = [field for field in required_fields if field not in data or not data[field].strip()]
    if missing_fields:
        return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400

    name = data["name"].strip()
    roll_no = data["roll_no"].strip()
    email = data["email"].strip()

    # Load template image: first try URL then fallback to local path.
    template_image = None
    if "template_image_url" in data and data["template_image_url"]:
        template_image = download_template_image(data["template_image_url"])
        if template_image is None:
            return jsonify({"error": "Failed to download template image from URL"}), 400
    elif "template_image_path" in data and data["template_image_path"]:
        template_path = data["template_image_path"]
        if not os.path.exists(template_path):
            return jsonify({"error": f"Template image not found at {template_path}"}), 400
        template_image = Image.open(template_path)
    else:
        return jsonify({"error": "No template image provided"}), 400

    image_size = data.get("image_size")  # optional dictionary with width and height
    qr_config = data.get("qr_config")    # optional dict for QR code configuration
    ticket_details = data.get("ticket_details", {})

    # Load existing ticket keys to avoid duplicates
    existing_keys = load_ticket_keys(KEY_FILE)

    # Generate ticket with QR code overlay
    ticket_number, output_path, qr_data = generate_ticket_qr(
        name, roll_no, email,
        template_image,
        image_size=image_size,
        qr_config=qr_config,
        ticket_details=ticket_details,
        existing_keys=existing_keys
    )

    # Optionally send the ticket via email if requested and credentials are provided
    if data.get("send_email", False) and EMAIL_USER and EMAIL_PASSWORD:
        subject = f"Your {ticket_details.get('event', 'Event')} Ticket"
        body = f"Dear {name},\n\nPlease find your ticket attached.\n\nTicket Details:\n{qr_data}\n\nThank you for registering!"
        try:
            send_email_with_attachment(subject, email, body, output_path)
        except Exception as e:
            # Log error but continue to return response
            print(f"Error sending email: {e}")

    # Construct a URL for the generated ticket (assuming the API is hosted appropriately)
    ticket_url = url_for('serve_generated_ticket', filename=os.path.basename(output_path), _external=True)

    response = {
        "ticket_number": ticket_number,
        "name": name,
        "roll_no": roll_no,
        "email": email,
        "ticket_url": ticket_url,
        "qr_data": qr_data
    }
    return jsonify(response), 200


# ---------------- Suggestions for Future Improvements ---------------- #
# 1. Add proper logging (e.g., using Python's logging module) for debugging and auditing.
# 2. Use request validation libraries (such as Marshmallow or pydantic) to validate and sanitize input data.
# 3. Consider hosting the generated images in cloud storage (e.g., AWS S3) for scalability.
# 4. Implement authentication and rate limiting for the API endpoints.
# 5. Refactor the code into separate modules (e.g., api.py, utils.py, config.py) for better maintainability.
# 6. Add unit tests to ensure the ticket generation functionality works as expected.
# 7. Use asynchronous request handling if expecting a high load (e.g., with FastAPI or using Flask’s async support).

# ---------------- Run the Flask App ---------------- #
if __name__ == "__main__":
    # For production, consider using a WSGI server like Gunicorn.
    app.run(host="0.0.0.0", port=5000, debug=True)
