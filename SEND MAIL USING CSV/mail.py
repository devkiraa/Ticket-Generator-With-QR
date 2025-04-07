import os
import csv
import time
import requests
from tqdm import tqdm
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API endpoint & auth
API_URL = os.getenv("API_URL")           # e.g. https://api.example.com/generate-ticket
API_KEY = os.getenv("API_KEY")           # if needed for Authorization

# Mail creds for the API to use when sending
MAIL_USER   = os.getenv("EMAIL_USER")    # e.g. mail.aeims@gmail.com
MAIL_PASS   = os.getenv("EMAIL_PASSWORD")
SENDER_NAME = os.getenv("SENDER_NAME", "Admin")

# Static defaults for your tickets (you can also pull these from .env if you like)
IMAGE_SIZE = {"width": 2000, "height": 647}
QR_CONFIG  = {
    "size": 350,
    "offset": {"x": 100, "y": 150},
    "rotation": 0
}

def process_and_request(csv_file):
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in tqdm(reader, desc="Sending API requests"):
            # read your CSV columns
            name          = row["name"].strip()
            gender        = row["gender"].strip()
            roll_no       = row["rollNo"].strip()
            email         = row["email"].strip()
            batch         = row["batch"].strip()
            year          = row["year"].strip()
            mobile        = row["mobile"].strip()
            template_path = row["template_image_path"].strip()
            event_name    = row["eventName"].strip()
            amount        = row["amount"].strip()

            # sanity check
            if not all([name, email, template_path, event_name, amount]):
                print(f"⚠️ Skipping incomplete row: {row}")
                continue

            # build the JSON payload exactly like your sample
            payload = {
                "email": email,
                "use_image_url": False,
                "template_image_path": template_path,
                "image_size": IMAGE_SIZE,
                "qr_config": QR_CONFIG,
                "ticket_details": {
                    "name": name,
                    "roll_no": roll_no,
                    "event": event_name,
                    "batch": batch,
                    "year": year,
                    "mobile": mobile
                },
                "mail_credentials": {
                    "email_user": MAIL_USER,
                    "email_password": MAIL_PASS,
                    "sender_name": SENDER_NAME
                },
                "send_email": True,
                "email_subject": f"Your Ticket for {event_name}",
                "email_body": (
                    "<div style=\"font-family:'Pricedown', Impact, sans-serif; "
                    "max-width:600px; margin:auto; background-color:#1a1a1a; "
                    "border-radius:10px; overflow:hidden; text-align:center; color:#f2f2f2;\">"
                    "<div style=\"background: url('{banner_link}') center center / cover no-repeat; height:200px;\"></div>"
                    "<div style=\"padding:20px;\">"
                    f"<h2 style=\"color:#ffc107; margin-bottom:10px;\">Hey {name}! 🎉</h2>"
                    "<p style=\"font-size:16px; color:#ffffff;\">Your ticket is ready for an epic college event!</p>"
                    f"<p style=\"font-size:14px; color:#d4d4d4; line-height:1.5;\">"
                    f"Roll No: <strong>{roll_no}</strong> <br>"
                    f"Batch: <strong>{batch}</strong> <br>"
                    f"Year: <strong>{year}</strong> <br>"
                    f"Mobile: <strong>{mobile}</strong></p>"
                    f"<p style=\"font-size:16px; color:#ffffff; line-height:1.5;\">"
                    f"Event: <strong>{event_name}</strong></p>"
                    "<p style=\"font-size:16px; color:#ffffff;\">Save your ticket, show it at the entry, "
                    "and get ready for a legendary experience!</p>"
                    "<p style=\"font-size:14px; color:#cccccc;\">Need any help? "
                    "Reach out to our support team at +9162383114481.</p>"
                    "<a href=\"https://your-support-link.com\" "
                    "style=\"display:inline-block; padding:10px 20px; background-color:#ffc107; "
                    "color:#1a1a1a; text-decoration:none; border-radius:5px; font-size:14px; margin-top:10px;\">"
                    "Contact Support</a>"
                    "<p style=\"font-size:12px; color:#999999; margin-top:20px;\">"
                    "Powered by <strong>SAVISHKAARA Tech Team</strong> 🚀</p>"
                    "</div></div>"
                ),
                "email_format": "html"
            }

            # send to your ticket‐generation API
            try:
                resp = requests.post(API_URL, json=payload, headers=headers, timeout=60)
                resp.raise_for_status()
                print(f"✅ Ticket/email requested for {email}")
            except Exception as e:
                print(f"❌ API error for {email}: {e}")

            time.sleep(1)  # avoid hammering your API

def main():
    process_and_request("mail.csv")

if __name__ == "__main__":
    main()
