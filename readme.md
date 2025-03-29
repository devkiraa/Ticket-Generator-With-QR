# Usage Instructions

## Introduction
This repository contains a CSV file named `data.csv`, which is structured to have at least three columns with specific column names: "NAME", "EVENT", and "template-id".

## data.csv
The `data.csv` file is located in the root directory of this repository. It contains sample data with the required column structure. 

### Column Names
- **NAME**: Represents the name of the individual or entity associated with an event.
- **EVENT**: Represents the type of event (e.g., Birthday, Wedding, Graduation).
- **template-id**: Represents an identifier for a specific template associated with the event.

### Important Note
Please ensure that any modifications made to the `data.csv` file adhere to the following guidelines:
- The file must maintain the `.csv` extension.
- The file must contain at least three columns.
- The column names must exactly match the following: "NAME", "EVENT", and "template-id".

## Usage
You can use the provided `data.csv` file for various purposes such as data analysis, testing, or as sample data for your projects. Simply download or clone this repository to access the `data.csv` file.

## Example
Below is a preview of how the `data.csv` file might look:

---

# `/generate_ticket` Endpoint Documentation

This endpoint generates a ticket with an overlaid QR code and optionally sends it by email. The ticket details are stored in a CSV file, and the generated image is saved in the `Qr_Generated` folder. The endpoint accepts a JSON payload and returns details including the ticket number and URL to view the ticket image.

## Endpoint URL

```
POST http://<your_server>:5000/generate_ticket
```

## Request Headers

- **Content-Type:** `application/json`

## JSON Request Payload

Below is a sample JSON payload. Adjust the values as needed:

```json
{
  "email": "user@example.com",
  "use_image_url": true,
  "template_image_url": "https://example.com/template.jpg",
  "image_size": {
    "width": 1240,
    "height": 480
  },
  "qr_config": {
    "size": 150,
    "offset": {
      "x": 1000,
      "y": 190
    },
    "rotation": 0
  },
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
```

### Field Descriptions

- **email**: Recipient's email address.
- **use_image_url**: Boolean flag. Set to `true` if you are providing a URL for the template image.
- **template_image_url**: URL of the image template (used if `use_image_url` is `true`).
- **image_size**: (Optional) Object specifying the width and height to resize the template image.
- **qr_config**: (Optional) Object containing:
  - **size**: Pixel size of the QR code.
  - **offset**: Object with `x` and `y` offsets (from the bottom-right corner).
  - **rotation**: (Optional) Angle in degrees to rotate the QR code.
- **ticket_details**: Object containing details to be embedded in the QR code (e.g., name, roll_no, event, extra info). The generated ticket number is automatically added to this object.
- **mail_credentials**: (Optional) Object with:
  - **email_user**: Email address used for sending.
  - **email_password**: Password (or app-specific password) for the sender email.
  - **sender_name**: Name displayed as the sender.
- **send_email**: Boolean flag. If `true`, an email with the ticket attachment is sent.
- **email_subject**: Subject for the ticket email.
- **email_body**: Body content (can be HTML if `email_format` is set to `"html"`).
- **email_format**: Either `"plain"` or `"html"` depending on the format of the email body.

## Response

On success, the endpoint returns a JSON response with the following fields:

- **email**: The email address provided in the request.
- **email_status**: Status of the email sending process (e.g., "Not sent" or success message).
- **qr_data**: The ticket details (in lowercase keys) embedded in the QR code.
- **ticket_number**: The unique ticket number generated.
- **ticket_url**: The URL to access the generated ticket image.

### Sample Successful Response

```json
{
  "email": "user@example.com",
  "email_status": "Email sent to user@example.com with attachment Qr_Generated/SampleEvent_12345_AB12CD34.png",
  "qr_data": {
    "name": "John Doe",
    "roll_no": "12345",
    "event": "SampleEvent",
    "extra": "Additional info if needed",
    "ticket_number": "AB12CD34"
  },
  "ticket_number": "AB12CD34",
  "ticket_url": "http://<your_server>:5000/generated/SampleEvent_12345_AB12CD34.png"
}
```

## Making a Request

You can test this endpoint using tools like [Postman](https://www.postman.com/) or `curl`.

### Example Using `curl`

```bash
curl -X POST http://<your_server>:5000/generate_ticket \
     -H "Content-Type: application/json" \
     -d '{
           "email": "user@example.com",
           "use_image_url": true,
           "template_image_url": "https://example.com/template.jpg",
           "image_size": {"width": 1240, "height": 480},
           "qr_config": {"size": 150, "offset": {"x": 1000, "y": 190}, "rotation": 0},
           "ticket_details": {"name": "John Doe", "roll_no": "12345", "event": "SampleEvent", "extra": "Additional info if needed"},
           "mail_credentials": {"email_user": "sender@example.com", "email_password": "password", "sender_name": "Admin"},
           "send_email": true,
           "email_subject": "Your Ticket for SampleEvent",
           "email_body": "<p>Dear John Doe,<br>Please find your ticket attached.</p>",
           "email_format": "html"
         }'
```

---