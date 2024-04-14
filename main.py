import csv
import qrcode
import random
import string
from PIL import Image

def generate_ticket_qr(row, template_path, output_path):
    # Generate a random alphanumeric ticket number with length 8
    ticket_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    # Generate QR data with NAME, ID, and the generated ticket number
    qr_data = f"NAME: {row['NAME']}, ID: {row['ID']}, Ticket Number: {ticket_number}"

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
    qr_position = (template_image.width - qr_image.width - 50, template_image.height - qr_image.height - 50)
    
    # Paste QR code onto the template
    template_image.paste(qr_image, qr_position)
    
    # Save the modified template
    template_image.save(output_path)

    return row['NAME'], ticket_number

def main():
    template_path = 'ticket_template.png'  # Path to your ticket template image

    # Load data from CSV
    tickets = []
    with open('data.csv', mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            # Generate QR code for each row in the CSV
            output_path = f"Qr Generated/ticket-{row['ID']}.png"
            name, ticket_number = generate_ticket_qr(row, template_path, output_path)
            tickets.append([name, ticket_number])

    # Write tickets data to a new CSV file
    with open('tickets.csv', mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['NAME', 'Ticket Number'])
        writer.writerows(tickets)

if __name__ == "__main__":
    main()
