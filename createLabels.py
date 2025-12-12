import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
import requests
import base64
import json
import os
import io
import shutil
import csv
from datetime import datetime
from PyPDF2 import PdfReader, PdfWriter
import argparse

# ======================================================================
# Warehouse Configuration
# ======================================================================

WAREHOUSE_CONFIG = {
    "1": {
        "sender_name": "GrabNest",
        "sender_email": "grabnest81@gmail.com",
        "address_line1": "6 Envision Cl",
        "suburb": "Pakenham",
        "state_name": "VIC",
        "postcode": "3810",
        "country": "AU",
        "label_sender_block": [
            # "IF UNDELIVERED RETURN TO:",
            # "GrabNest",
            # "6 Envision Cl",
            # "Pakenham",
            # "VIC 3810"
            "",
            "",
            "",
            "",
            ""
        ],
        "quote_pickup_suburb": "Pakenham",
        "quote_pickup_postcode": "3810"
    },
    "2": {
        "sender_name": "NexGen",
        "sender_email": "nexgenau23@gmail.com",
        "address_line1": "PO BOX 318",
        "suburb": "Glen Huntly",
        "state_name": "VIC",
        "postcode": "3163",
        "country": "AU",
        "label_sender_block": [
            "IF UNDELIVERED RETURN TO:",
            "NexGenAU",
            "PO BOX 318",
            "GLEN HUNTLY",
            "VIC 3163"
        ],
        "quote_pickup_suburb": "CARNEGIE",
        "quote_pickup_postcode": "3163"
    }
}

# ======================================================================
# Constants
# ======================================================================

CSV_FILENAME = "sendle_batch_csv_template.csv"
OUTPUT_FILENAME = f"{datetime.now().strftime('%Y%m%d')}_basic.pdf"
LINE_SPACING = 14
SAFE_WIDTH = 250
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SENDLE_DIR = os.path.join(BASE_DIR, "sendles")
SECRETS_PATH = os.path.join(os.path.dirname(__file__), "secrets.json")


def ensure_sendle_dir():
    if not os.path.exists(SENDLE_DIR):
        os.makedirs(SENDLE_DIR)


# empty default until CLI loads
SENDER_INFO = [" ", " ", " ", " ", " "]

# Tracking
sp = [['Basic', ' ', ' ', ' ', ' ']]
sd = [['Sendle', ' ', ' ', ' ', ' ']]

# ======================================================================
# Load API Keys
# ======================================================================

with open(SECRETS_PATH, "r") as f:
    secrets = json.load(f)

SENDLE_ID = secrets["SENDLE_ID"]
API_KEY = secrets["API_KEY"]

SENDLE_API_QUOTE_URL = "https://api.sendle.com/api/quote"
SENDLE_API_ORDER_URL = "https://api.sendle.com/api/orders"

# ======================================================================
# API Functions
# ======================================================================

def get_sendle_quote(pickup_suburb, pickup_postcode, delivery_suburb, delivery_postcode, weight, length, width, height):
    payload = {
        "pickup_suburb": pickup_suburb,
        "pickup_postcode": pickup_postcode,
        "delivery_suburb": delivery_suburb,
        "delivery_postcode": delivery_postcode,
        "weight_value": float(weight),
        "weight_units": "kg",
        "length": length,
        "width": width,
        "height": height,
        "dimension_units": "cm"
    }
    auth = base64.b64encode(f"{SENDLE_ID}:{API_KEY}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

    response = requests.get(SENDLE_API_QUOTE_URL, params=payload, headers=headers)
    return response.json()


def create_sendle_order(row, config):
    order_payload = {
        "pickup_option": "drop_off",
        "product_code": "STANDARD-DROPOFF",
        "description": row["customer_reference"],
        "customer_reference": row["customer_reference"],
        "kilogram_weight": 0.2,
        "cubic_metre_volume": 0.001,
        "sender": {
            "contact": {
                "name": config["sender_name"],
                "email": config["sender_email"]
            },
            "address": {
                "address_line1": config["address_line1"],
                "suburb": config["suburb"],
                "state_name": config["state_name"],
                "postcode": config["postcode"],
                "country": config["country"]
            }
        },
        "receiver": {
            "contact": {
                "name": row["receiver_name"],
                "email": config["sender_email"]
            },
            "address": {
                "address_line1": row["receiver_address_line1"],
                "suburb": row["receiver_suburb"],
                "state_name": row["receiver_state_name"],
                "postcode": row["receiver_postcode"],
                "country": "AU"
            }
        },
        "return_instructions": "Return to sender"
    }

    auth = base64.b64encode(f"{SENDLE_ID}:{API_KEY}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
    response = requests.post(SENDLE_API_ORDER_URL, json=order_payload, headers=headers)

    print("\t[*] Order request:", order_payload)
    print("\t[*] Order response:", response.status_code, response.text)

    return response.json()


def extract_label_url(order_response, preferred_size="a4"):
    labels = order_response.get("labels", [])
    if isinstance(labels, list) and labels:
        for lbl in labels:
            if lbl.get("format") == "pdf" and lbl.get("size") == preferred_size:
                return lbl.get("url")
        return labels[0].get("url")
    return None


def download_sendle_label(label_url, order_ref):
    ensure_sendle_dir()
    filename = os.path.join(SENDLE_DIR, f"{order_ref}.pdf")

    auth = base64.b64encode(f"{SENDLE_ID}:{API_KEY}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Accept": "application/pdf"}

    try:
        response = requests.get(label_url, headers=headers, stream=True, timeout=30)
        if response.status_code != 200:
            print(f"Failed to download label for {order_ref}: {response.status_code}")
            snippet = (response.text[:300] + '...') if response.text else "no response body"
            print("Response snippet:", snippet)
            return None

        with open(filename, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        print(f"Downloaded Sendle label → {filename}")
        return filename

    except requests.RequestException as e:
        print(f"Network error downloading Sendle label for {order_ref}: {e}")
        return None


def combine_sendle_pdfs(output_filename):
    if not os.path.exists(SENDLE_DIR):
        print("No Sendle labels found.")
        return

    sendle_pdfs = sorted(
        [os.path.join(SENDLE_DIR, f) for f in os.listdir(SENDLE_DIR) if f.endswith(".pdf")]
    )

    if not sendle_pdfs:
        print("No Sendle labels found.")
        return

    writer = PdfWriter()
    for path in sendle_pdfs:
        with open(path, "rb") as f:
            reader = PdfReader(f)
            for page in reader.pages:
                writer.add_page(page)

    with open(output_filename, "wb") as f:
        writer.write(f)

    print(f"Combined {len(sendle_pdfs)} Sendle labels into {output_filename}")


def clear_sendle_dir():
    if os.path.exists(SENDLE_DIR):
        shutil.rmtree(SENDLE_DIR)
        print("Cleared sendles/ directory.")


# ======================================================================
# Helper Functions
# ======================================================================

def wrap_text(text, font_name, font_size, max_width):
    lines = simpleSplit(str(text), font_name, font_size, max_width)
    if len(lines) == 1 and len(lines[0]) > 40:
        raw = lines[0]
        approx_chars = int(max_width / (font_size * 0.6))
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

    c.setFont("Helvetica", 12)
    c.drawString(margin_left, current_y, f"To: {data['receiver_name']}")
    current_y -= LINE_SPACING
    c.drawString(margin_left, current_y, data['receiver_address_line1'])
    current_y -= LINE_SPACING
    c.drawString(margin_left, current_y, data['receiver_suburb'])
    current_y -= LINE_SPACING
    c.drawString(margin_left, current_y, f"{data['receiver_state_name']} {data['receiver_postcode']}")

    current_y -= LINE_SPACING * 2

    for line in sender_info:
        c.drawString(margin_left, current_y, line)
        current_y -= LINE_SPACING

    current_y -= LINE_SPACING * 2

    c.drawString(margin_left, current_y, "Ref:")
    current_y -= LINE_SPACING
    return draw_wrapped_reference(c, data["customer_reference"], margin_left, current_y)


# ======================================================================
# Main Processing
# ======================================================================

def generate_labels(csv_filename, output_filename, config, price_threshold=6.0):
    df = pd.read_csv(csv_filename)

    required_cols = [
        "receiver_name",
        "receiver_address_line1",
        "receiver_suburb",
        "receiver_state_name",
        "receiver_postcode",
        "customer_reference",
        "description"
    ]

    df = df[required_cols]
    c = canvas.Canvas(output_filename, pagesize=A4)

    for _, row in df.iterrows():
        quote_response = get_sendle_quote(
            pickup_suburb=config["quote_pickup_suburb"],
            pickup_postcode=config["quote_pickup_postcode"],
            delivery_suburb=row["receiver_suburb"],
            delivery_postcode=row["receiver_postcode"],
            weight=0.2,
            length=10,
            width=10,
            height=10
        )

        try:
            if isinstance(quote_response, list) and quote_response:
                quote_price = float(quote_response[0].get("quote", {}).get("gross", {}).get("amount", 999))
            else:
                quote_price = float(quote_response.get("quote", {}).get("gross", {}).get("amount", 999))
        except Exception:
            quote_price = 999

        print(f"Quote for {row['receiver_name']}: ${quote_price:.2f}")

        order_id = row["description"]
        receiver = row["receiver_name"]

        label_url = ""
        tracking_url = ""
        sendle_ref = ""

        if quote_price < price_threshold:
            order_response = create_sendle_order(row, config)
            tracking_url = order_response.get("tracking_url")
            label_url = extract_label_url(order_response)
            sendle_ref = order_response.get("sendle_reference", row["customer_reference"])

        if label_url:
            download_sendle_label(label_url, sendle_ref)
            sd.append([order_id, ' ', ' ', receiver, sendle_ref, ' ', ' ', tracking_url])
        else:
            draw_label(c, row, SENDER_INFO)
            sp.append([order_id, ' ', ' ', receiver, ' '])
            c.showPage()

    c.save()
    print(f"Basic Parcel PDF created: {output_filename}")

    sendle_output = f"{datetime.now().strftime('%Y%m%d')}_sendle.pdf"
    combine_sendle_pdfs(sendle_output)
    print(f"Sendle labels PDF created: {sendle_output}")
    clear_sendle_dir()

    with open('tracking_update.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(sp)
        writer.writerow([])
        writer.writerows(sd)


# ======================================================================
# Entry Point
# ======================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate labels and Sendle orders.")
    parser.add_argument(
        "--warehouse",
        required=True,
        choices=["1", "2"],
        help="Select which warehouse's sender information to use. 1 = Pakenham 2 = Carnegie "
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=7.0,
        help="Maximum Sendle quote price before falling back to basic label (default: 6.0)"
    )

    args = parser.parse_args()
    config = WAREHOUSE_CONFIG[args.warehouse]

    SENDER_INFO = config["label_sender_block"]

    generate_labels(CSV_FILENAME, OUTPUT_FILENAME, config, price_threshold=args.threshold)
