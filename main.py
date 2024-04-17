import csv
import qrcode
import random
import string
from PIL import Image
import os
from tqdm import tqdm  # Import tqdm for progress tracking

def generate_ticket_qr(row, template_folder, output_folder):
    # Skip rows with empty template-id
    if not row['template-id']:
        print(f"Template ID is empty for row: {row}")
        return None, None

    # Generate a random alphanumeric ticket number with length 8
    ticket_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    # Generate QR data with NAME, EVENT, and the generated ticket number
    qr_data = f"NAME: {row['NAME']}, EVENT: {row['EVENT']}, Ticket Number: {ticket_number}"

    # Construct template path
    template_id = row.get('template-id', '')  # Get template ID, default to empty string if not found
    template_path = os.path.join(template_folder, f"{template_id}.png")

    # Check if template path exists
    if not os.path.exists(template_path):
        print(f"Template image not found for row: {row}")
        return None, None

    # Load the template image
    template_image = Image.open(template_path)

    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white")
    
    # Resize QR code
    qr_image = qr_image.resize((150, 150))
    
    # Calculate position to paste QR code (bottom right corner)
    qr_position = (template_image.width - qr_image.width - 50, template_image.height - qr_image.height - 120)
    
    # Paste QR code onto the template
    template_image.paste(qr_image, qr_position)
    
    # Generate output file name with a unique identifier
    ticket_id = f"SAVISHKAARA#230{row['ID']}_{ticket_number}.png"
    
    # Save the modified template
    output_path = os.path.join(output_folder, ticket_id)
    template_image.save(output_path)

    return ticket_number, ticket_id


def main():
    template_folder = 'Template'  # Path to your ticket template folder
    output_folder = 'Qr Generated'  # Path to output folder

    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Load data from CSV
    tickets = []
    with open('data.csv', mode='r') as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        if not rows:
            print("No data found in the CSV file.")
            return  # Exit the function if there are no rows in the CSV file
        
        # Use tqdm for progress tracking
        for row in tqdm(rows, desc="Generating Tickets", total=len(rows)):
            # Generate QR code for each row in the CSV
            ticket_number, ticket_id = generate_ticket_qr(row, template_folder, output_folder)
            row['Ticket Number'] = ticket_number  # Add ticket number to the row
            row['Ticket-ID'] = ticket_id  # Add ticket ID (image file name) to the row
            tickets.append(row)  # Append the updated row to the tickets list

    # Write tickets data to a new CSV file
    with open('tickets.csv', mode='w', newline='') as file:
        if tickets:  # Check if there are any tickets before writing to the CSV file
            fieldnames = list(tickets[0].keys())  # Get field names from the first row
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(tickets)
        else:
            print("No tickets generated.")


if __name__ == "__main__":
    main()
