import pandas as pd
import re
from datetime import datetime
import os

def is_valid_id(id_str):
    """
    Checks if the ID is exactly 8 alphanumeric characters.
    """
    return bool(re.match(r'^[A-Za-z0-9]{8}$', str(id_str)))

def find_file_case_insensitive(filename):
    """
    Searches for a file in the current directory, ignoring case.
    Returns the actual filename if found, else raises an error.
    """
    lower_target = filename.lower()
    for f in os.listdir('.'):
        if f.lower() == lower_target:
            return f
    raise FileNotFoundError(f"File matching '{filename}' (case-insensitive) not found in current directory.")

def carrier_from_tracking(tracking_number):
    """
    Returns the carrier based on the format of the tracking number.
    """
    if isinstance(tracking_number, str) and re.fullmatch(r'[A-Za-z0-9]{7}', tracking_number):
        return 'SENDLE'
    else:
        return 'AUP'

def normalize_tracking_number(x):
    """
    Ensures tracking number is string and converts scientific notation if needed.
    """
    try:
        if isinstance(x, float) or re.match(r'^\d+(\.\d+)?[eE]\+?\d+$', str(x)):
            return format(int(float(x)), 'f').rstrip('.0')
        return str(x).strip()
    except:
        return ''

def generate_dispatch_file_with_tracking(merged_csv_path, kogan_csv_path, tracking_csv_path, dispatch_csv_path):
    """
    Generates a dispatch file from merged_labels.csv, kogan_orders.csv, and tracking.csv.
    """
    # Load merged labels
    merged_df = pd.read_csv(merged_csv_path)
    merged_df['amt'] = pd.to_numeric(merged_df['amt'], errors='coerce')

    # Filter: amt >= TRACKING_AMT and valid ID format
    filtered_df = merged_df[(merged_df['id'].apply(is_valid_id))].copy()
    if filtered_df.empty:
        print("No valid dispatch entries found after filtering.")
        return

    # Load kogan_orders.csv
    kogan_csv_path = find_file_case_insensitive(kogan_csv_path)
    kogan_df = pd.read_csv(kogan_csv_path, dtype=str)
    kogan_df['Quantity'] = pd.to_numeric(kogan_df['Quantity'], errors='coerce')

    required_kogan_cols = {'OrderID', 'ProductCode', 'Quantity'}
    if not required_kogan_cols.issubset(set(kogan_df.columns)):
        raise ValueError(f"{kogan_csv_path} must contain columns: {required_kogan_cols}")

    # Merge on id (merged) and OrderID (kogan)
    enriched_df = pd.merge(filtered_df, kogan_df[['OrderID', 'ProductCode', 'Quantity']],
                           left_on='id', right_on='OrderID', how='inner')

    # Load tracking.csv
    tracking_csv_path = find_file_case_insensitive(tracking_csv_path)
    tracking_df = pd.read_csv(tracking_csv_path, dtype={'Tracking Number': str})
    tracking_df.columns = tracking_df.columns.str.strip()

    # Normalize tracking numbers
    tracking_df['Tracking Number'] = tracking_df['Tracking Number'].apply(normalize_tracking_number)

    required_tracking_cols = {'ID', 'Tracking Number'}
    if not required_tracking_cols.issubset(set(tracking_df.columns)):
        raise ValueError(f"{tracking_csv_path} must contain columns: {required_tracking_cols}")

    # Merge tracking info
    enriched_df = pd.merge(enriched_df, tracking_df[['ID', 'Tracking Number']],
                           left_on='id', right_on='ID', how='left')

    # Build final DataFrame
    final_df = pd.DataFrame()
    final_df['CONNOTE'] = enriched_df['Tracking Number'].fillna('ELMS')
    final_df['ITEM'] = enriched_df['ProductCode']
    final_df['SERIAL_NUMBER'] = ''
    final_df['DISPATCH_DATE'] = datetime.today().strftime('%d/%m/%Y')
    final_df['ORDER_ID'] = enriched_df['id']
    final_df['QUANTITY'] = enriched_df['Quantity']
    final_df['WAREHOUSE'] = 'AUNEX'
    final_df['CARRIER'] = enriched_df['Tracking Number'].apply(carrier_from_tracking)
    final_df['amt'] = enriched_df['amt']

    # Save final output
    final_df.to_csv(dispatch_csv_path, index=False)
    print(f"Dispatch file saved to: {dispatch_csv_path}")

# Example usage
merged_csv = 'merged_labels.csv'
kogan_csv = 'kogan_orders.csv'
tracking_csv = 'tracking.csv'
dispatch_csv = 'dispatch.csv'

generate_dispatch_file_with_tracking(merged_csv, kogan_csv, tracking_csv, dispatch_csv)
