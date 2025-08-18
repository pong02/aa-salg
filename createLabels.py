import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit

# Constants
CSV_FILENAME = "sendle_batch_csv_template.csv"
OUTPUT_FILENAME = "shipping_labels_output.pdf"
LINE_SPACING = 14
SAFE_WIDTH = 250  # conservative printable width in points

# SENDER_INFO = [
#     "From: TheAroundAustralia",
#     "Vision Apartments",
#     "500 Elizabeth Street",
#     "MELBOURNE",
#     "VIC 3000"
# ]

SENDER_INFO = [
    " ",
    " ",
    " ",
    " ",
    " "
]

def wrap_text(text, font_name, font_size, max_width):
    """
    Fallback wrapper: uses simpleSplit but also splits unbroken lines if needed.
    """
    lines = simpleSplit(str(text), font_name, font_size, max_width)
    
    # Handle unbroken long strings (e.g., long tracking numbers with no spaces)
    if len(lines) == 1 and len(lines[0]) > 40:
        raw = lines[0]
        approx_chars = int(max_width / (font_size * 0.6))  # rough width-per-char estimate
        lines = [raw[i:i+approx_chars] for i in range(0, len(raw), approx_chars)]
    
    return lines

def draw_wrapped_reference(c, text, x, y, font="Helvetica", size=12, max_width=SAFE_WIDTH):
    lines = wrap_text(text, font, size, max_width)
    for line in lines:
        c.setFont(font, size)
        c.drawString(x, y, line)
        y -= LINE_SPACING
    return y

def draw_label(c, data, sender_info):
    width, height = A4
    margin_left = 90
    current_y = height - 100

    # Recipient block
    c.setFont("Helvetica", 12)
    c.drawString(margin_left, current_y, f"To: {data['receiver_name']}")
    current_y -= LINE_SPACING
    c.drawString(margin_left, current_y, data['receiver_address_line1'])
    current_y -= LINE_SPACING
    c.drawString(margin_left, current_y, data['receiver_suburb'])
    current_y -= LINE_SPACING
    c.drawString(margin_left, current_y, f"{data['receiver_state_name']} {data['receiver_postcode']}")

    # Spacer
    current_y -= LINE_SPACING * 2

    # Sender block
    for line in sender_info:
        c.drawString(margin_left, current_y, line)
        current_y -= LINE_SPACING

    # Spacer
    current_y -= LINE_SPACING * 2

    # Ref block
    c.drawString(margin_left, current_y, "Ref:")
    current_y -= LINE_SPACING
    current_y = draw_wrapped_reference(
        c, data["customer_reference"], margin_left, current_y
    )

def generate_labels(csv_filename, output_filename):
    df = pd.read_csv(csv_filename)

    required_cols = [
        "receiver_name",
        "receiver_address_line1",
        "receiver_suburb",
        "receiver_state_name",
        "receiver_postcode",
        "customer_reference"
    ]
    df = df[required_cols]

    c = canvas.Canvas(output_filename, pagesize=A4)

    for _, row in df.iterrows():
        draw_label(c, row, SENDER_INFO)
        c.showPage()

    c.save()
    print(f"PDF created: {output_filename}")

# Run the generator
generate_labels(CSV_FILENAME, OUTPUT_FILENAME)
