import csv
import qrcode
import random
import string
from PIL import Image
import os

def generate_ticket_qr(row, template_folder, output_folder):
    # Generate a random alphanumeric ticket number with length 8
    ticket_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    # Generate QR data with NAME, EVENT, and the generated ticket number
    qr_data = f"NAME: {row['NAME']}, EVENT: {row['EVENT']}, Ticket Number: {ticket_number}"

    # Load the template image
    template_path = os.path.join(template_folder, f"{row['template-id']}.png")
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
    qr_position = (template_image.width - qr_image.width - 50, template_image.height - qr_image.height - 50)
    
    # Paste QR code onto the template
    template_image.paste(qr_image, qr_position)
    
    # Save the modified template
    output_path = os.path.join(output_folder, f"ticket-{row['ID']}.png")
    template_image.save(output_path)

    return ticket_number

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
        for row in reader:
            # Generate QR code for each row in the CSV
            ticket_number = generate_ticket_qr(row, template_folder, output_folder)
            row['Ticket Number'] = ticket_number  # Add ticket number to the row
            tickets.append(row)

    # Write tickets data to a new CSV file
    with open('tickets.csv', mode='w', newline='') as file:
        fieldnames = list(tickets[0].keys())  # Get field names from the first row
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(tickets)

if __name__ == "__main__":
    main()
