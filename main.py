import gspread
import qrcode
import random
import string
from PIL import Image
import os
import time
import csv
from tqdm import tqdm


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


def generate_ticket_qr(row, template_id, template_folder, output_folder):
    ticket_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
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

    return ticket_number, ticket_id


def process_sheet(sheet_url, template_id, processed_ids, output_sheet, template_folder, output_folder):
    # Access the sheet
    gc = gspread.service_account(filename="service_account.json")
    sheet = gc.open_by_url(sheet_url).sheet1

    # Retrieve rows
    rows = sheet.get_all_records()
    print(f"Retrieved {len(rows)} rows from {sheet_url}.")
    if not rows:
        print("No data found in the Google Sheet.")
        return

    for row in tqdm(rows, desc=f"Processing Sheet {sheet_url}"):
        row = normalize_columns(row)  # Normalize the columns

        # Check if required columns exist
        if 'Name' not in row or 'Roll-No' not in row or 'EMAIL' not in row:
            print(f"Required columns missing in sheet: {sheet_url}")
            continue

        # Skip if already processed
        unique_key = f"{row['Name']}_{row['Roll-No']}_{row['EMAIL']}"
        if unique_key in processed_ids:
            continue

        ticket_number, ticket_id = generate_ticket_qr(row, template_id, template_folder, output_folder)
        if ticket_number and ticket_id:
            # Add to the processed IDs and log into the output sheet
            processed_ids.add(unique_key)
            output_sheet.append_row([row['Name'], row['Roll-No'], row['EMAIL'], ticket_number, ticket_id])
            print(f"Ticket generated: {ticket_id}")


def main():
    # CSV containing template IDs and sheet URLs
    config_csv = "sheets_config.csv"

    # Paths
    template_folder = "Template"
    output_folder = "Qr Generated"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Output Google Sheet for processed data
    gc = gspread.service_account(filename="service_account.json")
    output_sheet = gc.open("Processed Tickets").sheet1

    # Initialize processed IDs
    processed_ids = set()

    # Read sheet configurations
    print("Loading sheet configurations...")
    with open(config_csv, mode="r") as file:
        reader = csv.DictReader(file)
        sheet_configs = list(reader)

    print("Monitoring multiple Google Sheets for new data...")
    while True:
        try:
            for config in sheet_configs:
                sheet_url = config.get("sheet_url")
                template_id = config.get("template-id")
                if not sheet_url or not template_id:
                    print(f"Invalid configuration: {config}")
                    continue

                process_sheet(sheet_url, template_id, processed_ids, output_sheet, template_folder, output_folder)

            time.sleep(10)  # Wait 30 seconds before checking again
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)  # Retry after a short delay


if __name__ == "__main__":
    main()
