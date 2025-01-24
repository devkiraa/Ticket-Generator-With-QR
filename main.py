import gspread
import qrcode
import random
import string
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

def normalize_columns(row):
    """
    Normalize column names to match expected headers.
    """
    normalized_row = {}
    column_mapping = {
        'name': 'Name',
        'id': 'Roll-No',
        'email': 'EMAIL',
    }

    for key, value in row.items():
        normalized_key = column_mapping.get(key.lower(), key)  # Normalize or keep as-is
        normalized_row[normalized_key] = value

    return normalized_row

def load_ticket_keys(key_file):
    """Load existing ticket keys from a CSV file."""
    ticket_keys = set()
    if os.path.exists(key_file):
        with open(key_file, mode="r") as file:
            reader = csv.reader(file)
            for row in reader:
                ticket_keys.add(row[0])
    return ticket_keys

def save_ticket_key(key_file, ticket_number):
    """Save a new ticket key to the CSV file with a timestamp."""
    with open(key_file, mode="a", newline="") as file:
        writer = csv.writer(file)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([ticket_number, timestamp])

def generate_unique_ticket_number(existing_keys):
    """Generate a unique ticket number."""
    while True:
        ticket_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if ticket_number not in existing_keys:
            return ticket_number

def generate_ticket_qr(row, template_id, template_folder, output_folder, existing_keys, key_file):
    ticket_number = generate_unique_ticket_number(existing_keys)
    qr_data = f"NAME: {row['Name']}, ROLL-NO: {row['Roll-No']}, EMAIL: {row['EMAIL']}, Ticket Number: {ticket_number}"
    template_path = os.path.join(template_folder, f"{template_id}.png")

    if not os.path.exists(template_path):
        print(f"Template image not found for template ID: {template_id}")
        return None, None

    template_image = Image.open(template_path)
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white")
    qr_image = qr_image.resize((150, 150))
    qr_position = (template_image.width - qr_image.width - 50, template_image.height - qr_image.height - 120)
    template_image.paste(qr_image, qr_position)
    ticket_id = f"SAVISHKAARA2K25#{row['Roll-No']}_{ticket_number}.png"
    output_path = os.path.join(output_folder, ticket_id)
    template_image.save(output_path)

    save_ticket_key(key_file, ticket_number)
    return ticket_number, output_path

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

def is_valid_row(row):
    """Check if all columns in the row have values."""
    return all(value.strip() for value in row.values())

def process_sheet(sheet_url, template_id, processed_ids, output_sheet, template_folder, output_folder, existing_keys, key_file):
    gc = gspread.service_account(filename="service_account.json")
    sheet = gc.open_by_url(sheet_url).sheet1

    rows = sheet.get_all_records()
    if not rows:
        return

    new_tickets_generated = 0

    for row in rows:
        row = normalize_columns(row)
        if not is_valid_row(row):
            print(f"Skipping row with missing values: {row}")
            continue

        if 'Name' not in row or 'Roll-No' not in row or 'EMAIL' not in row:
            print(f"Skipping invalid row: {row}")
            continue

        unique_key = f"{template_id}_{row['Name']}_{row['Roll-No']}_{row['EMAIL']}"
        if unique_key in processed_ids:
            continue

        ticket_number, ticket_path = generate_ticket_qr(row, template_id, template_folder, output_folder, existing_keys, key_file)
        if ticket_number and ticket_path:
            processed_ids.add(unique_key)
            existing_keys.add(ticket_number)
            output_sheet.append_row([row['Name'], row['Roll-No'], row['EMAIL'], ticket_number, os.path.basename(ticket_path)])
            send_email_with_attachment(
                f"Your {template_id} Event Ticket",
                row['EMAIL'],
                f"Dear {row['Name']},\n\nPlease find your ticket attached.\n\nThank you for registering!",
                ticket_path
            )
            new_tickets_generated += 1

    if new_tickets_generated > 0:
        print(f"Generated {new_tickets_generated} new tickets for template ID: {template_id}")
    else:
        print(f"No new rows to process for template ID: {template_id}.")

def main():
    # CSV containing template IDs and sheet URLs
    config_csv = "sheets_config.csv"
    key_file = "ticket_keys.csv"

    # Paths
    template_folder = "Template"
    output_folder = "Qr Generated"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Output Google Sheet for processed data
    gc = gspread.service_account(filename="service_account.json")
    output_sheet = gc.open("Processed Tickets").sheet1

    # Initialize processed IDs and load existing ticket keys
    processed_ids = set()
    existing_keys = load_ticket_keys(key_file)

    # Read sheet configurations
    print("Loading sheet configurations...")
    with open(config_csv, mode="r") as file:
        reader = csv.DictReader(file)
        sheet_configs = list(reader)

    print("Monitoring multiple templates for new data...")
    while True:
        try:
            for config in sheet_configs:
                sheet_url = config.get("sheet_url")
                template_id = config.get("template-id")
                if not sheet_url or not template_id:
                    print(f"Invalid configuration: {config}")
                    continue

                process_sheet(sheet_url, template_id, processed_ids, output_sheet, template_folder, output_folder, existing_keys, key_file)

            time.sleep(max(10, 30 / len(sheet_configs)))  # Adjust wait time based on the number of templates
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)  # Retry after a short delay

if __name__ == "__main__":
    main()
