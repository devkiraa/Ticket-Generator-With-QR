import csv
import json
import requests

API_URL = "https://ticket.savishkaara.in/generate_ticket"

# Constants that do not change
USE_IMAGE_URL = False
IMAGE_SIZE = { "width": 2000, "height": 647 }
QR_CONFIG = {
    "size": 350,
    "offset": { "x": 100, "y": 200 },
    "rotation": 0
}
MAIL_CREDENTIALS = {
    "email_user": "mail.aeims@gmail.com",
    "email_password": "hbpduroqycmyzxld",
    "sender_name": "Admin"
}
SEND_EMAIL = True
EMAIL_SUBJECT = "Your Ticket for SAVISHKAARA2K25"
EMAIL_BODY = """
<div style="font-family: Arial, sans-serif; max-width:600px; margin:auto; padding:20px; background-color:#f8f8f8; border-radius:10px; text-align:center;">
<h2 style="color:#fc8019; margin-bottom:10px;">Hey {name}! 🎉</h2>
<p style="color:#333; font-size:16px;">Your ticket is ready! We've attached it to this email, so you're all set for an amazing experience.</p>
<p style="color:#666; font-size:14px;">Event: <strong>{event}</strong> <br>Date & Time: <strong>11-04-2025, TBA</strong> <br>Venue: <strong>Event Location</strong></p>
<div style="margin:20px 0;">
<img src='https://your-dynamic-countdown-service.com/api?end=2025-04-11T00:00:00Z&template=swiggy' alt='Countdown Timer' style='max-width:100%; height:auto;'/>
</div>
<p style="color:#333; font-size:16px;">Save your ticket, show it at the entry, and get ready for a fantastic time!</p>
<p style="font-size:14px; color:#666;">Need any help? We’ve got your back! <br>Reach out to our support team anytime.</p>
<a href='https://your-support-link.com' style='display:inline-block; padding:10px 20px; background-color:#fc8019; color:#fff; text-decoration:none; border-radius:5px; font-size:14px; margin-top:10px;'>Contact Support</a>
<p style='font-size:12px; color:#999; margin-top:20px;'>Powered by <strong>Your Company Name</strong> 🚀</p>
</div>
"""
EMAIL_FORMAT = "html"

def send_ticket(data):
    try:
        response = requests.post(API_URL, json=data)
        if response.status_code == 200:
            print(f"✅ Ticket sent to {data['email']}")
        else:
            print(f"❌ Failed for {data['email']}: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Exception occurred: {str(e)}")

def main():
    with open("tickets.csv", newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            ticket_details = {
                "name": row["name"],
                "roll_no": row["rollNo"],
                "event": row["event"],
                "batch": row["batch"],
                "year": row["year"],
                "mobile": row["mobile"],
                "amount": row["amount"]
            }

            email_body_filled = EMAIL_BODY.format(name=row["name"], event=row["event"])

            payload = {
                "email": row["email"],
                "use_image_url": USE_IMAGE_URL,
                "template_image_path": row["template_image_path"],
                "image_size": IMAGE_SIZE,
                "qr_config": QR_CONFIG,
                "ticket_details": ticket_details,
                "mail_credentials": MAIL_CREDENTIALS,
                "send_email": SEND_EMAIL,
                "email_subject": EMAIL_SUBJECT,
                "email_body": email_body_filled,
                "email_format": EMAIL_FORMAT
            }

            send_ticket(payload)

if __name__ == "__main__":
    main()
