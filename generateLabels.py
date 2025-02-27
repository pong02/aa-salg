import os
import pandas as pd
import re

TRACKING_AMT = 15
# Define the standard column names for each platform
COLUMN_MAPPING = {
    'shopify': {
        'name': 'id', 'shipping name': 'rname',
        'billing company': 'bcompany', 'billing street': 'bstreet' ,
        'billing city': 'bcity', 'billing zip': 'bzip',
        'billing province': 'bstate', 'billing name': 'bname',
        'shipping street': 'street', 'shipping address 1': 'address1',
        'shipping address 2': 'address2', 'shipping company': 'company',
        'shipping city': 'city', 'shipping zip': 'zip',
        'shipping province': 'state', 'tags': 'tags',
        'lineitem sku': 'custom_label', 'lineitem quantity': 'Quantity',
        'shipping method': 'shipping_method', 'notes': 'notes', 'notes attribute': 'notes_attribute',
        'total':'amt'
    },
    'kogan': {
        'deliveryname': 'rname', 'deliveryaddress1': 'address1',
        'deliveryaddress2': 'address2', 'deliverysuburb': 'city',
        'deliverystate': 'state', 'deliverypostcode': 'zip',
        'quantity': 'Quantity', 'productcode': 'custom_label', 'labelinfo': 'id',
        'itemprice':'amt'
    },
    'ebay': {
        'order number': 'id', 'buyer username': 'buyer_username',
        'postage service': 'shipping_method', 'quantity': 'Quantity',
        'custom label': 'custom_label', 'post to name': 'rname',
        'post to address 1': 'address1', 'post to address 2': 'address2',
        'post to city': 'city', 'post to state': 'state',
        'post to postal code': 'zip',
        'sold for':'amt'
    },
    'catch': {
        'order number': 'id', 'quantity': 'Quantity',
        'offer sku': 'custom_label', 'shipping method': 'shipping_method',
        'shipping address first name': 'fname',
        'shipping address last name': 'lname',
        'shipping address company': 'company',
        'shipping address street 1': 'address1',
        'shipping address street 2': 'address2',
        'shipping address city': 'city',
        'shipping address state': 'state',
        'shipping address zip': 'zip',
        'total order amount incl. vat (including shipping charges)':'amt'
    }
}

def multiplyCustomLabel(row):
    """
    Multiplies the Quantity based on the multiplier in the custom_label.
    If no multiplier is specified, it assumes *1.
    Ensures the custom_label is not empty before processing.

    Parameters:
        row (pd.Series): A row from the DataFrame.

    Returns:
        str: Updated custom_label with quantities applied.
    """
    if not row['custom_label']:  # Check if custom_label is empty
        return row['custom_label']  # Return as is if no custom_label

    updated_labels = []
    custom_labels = row['custom_label'].split(',')  # Split multiple labels

    for label in custom_labels:
        multiplier = int(row['Quantity'])  # Default to the row's Quantity
        if '*' in label:  # Check if a multiplier is already present in the label
            updated_labels.append(label)  # Retain the label as is
        else:
            updated_labels.append(f"{label}*{int(multiplier)}")  # Add multiplier to the label

    return ', '.join(updated_labels)  # Join all updated labels with a comma

def isBlank (myString):
    return not (myString and myString.strip())

def extractEnv(value):
    """
    Extracts the second item inside [*]/[*] or the first [*] if only one pair exists.
    
    Parameters:
        value (str): The input string containing bracketed items.

    Returns:
        str: The extracted item or an empty string if no match is found.
    """
    if not isinstance(value, str):
        return ""  # Handle non-string inputs safely

    # Pattern for [*]/[*] or [*]
    match = re.search(r'\[(.*?)\](?:/\[(.*?)\])?', value)
    
    if match:
        if match.group(2):  # If the second group (after the slash) exists
            return match.group(2)
        return match.group(1)  # Otherwise, return the first group
    return ""  # Return empty if no match

def cleanCustomLabel(label):
    newLabel = label.replace('+',',').replace('(','[').replace(')',']').replace(' x','*').replace(' ','')
    return newLabel.strip('.').strip('/').strip(' ').strip()

def trackingUpgrade(envelope):
    if envelope == "C5":
        return "TMP-C5"
    elif envelope == "C4":
        return "Parcel-Medium"
    elif envelope == "Small":
        return "TMP-Small"
    elif envelope == "Parcel":
        return "Parcel-Medium"
    elif "parcel" in envelope.lower():
        return envelope # parcels are already tracked by default
    return envelope

def expressUpgrade(envelope):
    if envelope == "C4":
        return "Parcel-Express"
    elif "parcel" in envelope.lower():
        return "Parcel-Express" # parcels are already tracked by default
    return "Express"
    
def replaceLabel(customLabel,shipping):
    newEnv = ""
    oldEnv = extractEnv(customLabel)
    if shipping == "express": 
        newEnv = expressUpgrade(oldEnv)
    elif shipping == "tracking": 
        newEnv = trackingUpgrade(oldEnv)
    else:
        if "[Parcel]" in customLabel:
            return customLabel.replace("[Parcel]","[Parcel-Medium]") #force rewrite all [parcel]
        return customLabel
    return customLabel.replace(oldEnv,newEnv)
    
def addPlatform(customLabel,platformStr):
    if customLabel.count('[') > 1:
        return customLabel # This is already annotated, skip
    elif isBlank(customLabel):
        return ""
    elif customLabel.count('[') == 0:
        return "["+platformStr+"]/[?]"+customLabel
    
    return "["+platformStr+"]/"+customLabel
    
def process_file(filepath, platform):
    if platform == 'ebay':
        df = pd.read_csv(filepath, skiprows=[0, 2])
    else:
        df = pd.read_csv(filepath)

    df.columns = df.columns.str.lower()
    column_mapping = COLUMN_MAPPING.get(platform, {})
    filtered_columns = {col: column_mapping[col] for col in df.columns if col in column_mapping}
    df = df[list(filtered_columns.keys())]
    df.rename(columns=filtered_columns, inplace=True)

    df.fillna('', inplace=True)

    '''
        =============   Shopify   =============
    '''
    if platform == 'shopify':
        df['custom_label'] = df['custom_label'].astype(str).apply(lambda x: cleanCustomLabel(x))
        """
        handle shopify cases with NO SHIPPING DETAILS
        """
        df['address'] = df.apply(
            lambda row: f"{row['bcompany']} {row['bstreet']}" if pd.isna(row['street']) or row['street'].strip() == '' 
            else f"{row['company']} {row['street']}", 
            axis=1
        )
        df['city'] = df.apply(
            lambda row: row['bcity'] if pd.isna(row['city']) or row['city'].strip() == '' 
            else row['city'], 
            axis=1
        )

        df['zip'] = df.apply(
            lambda row: row['bzip'] if pd.isna(row['zip']) or row['zip'].strip() == '' 
            else row['zip'], 
            axis=1
        )

        df['state'] = df.apply(
            lambda row: row['bstate'] if pd.isna(row['state']) or row['state'].strip() == '' 
            else row['state'], 
            axis=1
        )

        df['rname'] = df.apply(
            lambda row: row['bname'] if pd.isna(row['rname']) or row['rname'].strip() == '' 
            else row['rname'], 
            axis=1
        )
        df['shipping_method'] = df['tags'].str.contains(r'kogan|mydeal', case=False, na=False).apply(
            lambda x: "tracking" if x else "untracked"
        )
        
        df['shipping_method'] = df['amt'].astype(float).apply(lambda x: 'tracking' if x >= TRACKING_AMT else 'untracked')
        df.loc[df['tags'].str.contains('mydeal', case=False, na=False), 'custom_label'] = (
            df['custom_label']
            .str.replace("TMP-Small", "C5", case=False)
            .str.replace("TMP-C5", "C5", case=False)
        )
        
        df['custom_label'] = df['custom_label'].str.replace(r'^\[SP\]/', '', regex=True)
        df['custom_label'] = df['custom_label'].astype(str).apply(lambda x: addPlatform(x, "SP"))
        df['custom_label'] = df.apply(lambda row: replaceLabel(row['custom_label'], row['shipping_method']), axis=1)
        df['zip'] = df['zip'].astype(str).str.extract(r'(\d{4})', expand=False)
        df['custom_label'] = df.apply(multiplyCustomLabel, axis=1)
        df['Quantity'] = 1


        '''
        =============   eBay   =============
        '''
    elif platform == 'ebay':
        df['custom_label'] = df['custom_label'].astype(str).apply(lambda x: cleanCustomLabel(x))
        df = df[~df['id'].str.contains('record\\(s\\) downloaded', case=False, na=False)]
        df['amt'] = pd.to_numeric(df['amt'].str.replace('AU $', '', regex=False), errors='coerce')
        df['amt'].fillna(0, inplace=True)
        df['address'] = df.apply(
            lambda row: row['address1'] + ' ' + row['address2'] if 'ebay:' not in row['address1'].lower() else row['address2'],
            axis=1
        )
        shippingMethod = df['shipping_method'].str.lower()
        df['shipping_method'] = shippingMethod.apply(
            lambda x: 
                "untracked" if "untracked" in x
                else "tracking" if "tracked" in x or "tracking" in x
                else "express" if "express" in x
                else ""
        )
        df['shipping_method'] = df.apply(
            lambda row: 'tracking' if row['amt'] >= TRACKING_AMT and row['shipping_method'] != 'tracking' 
                        else row['shipping_method'], 
            axis=1
        )
        df['custom_label'] = df['custom_label'].str.replace(r'^\[NG\]/', '', regex=True)
        df['custom_label'] = df['custom_label'].astype(str).apply(lambda x: addPlatform(x, "NG"))
        df['custom_label'] = df.apply(lambda row: replaceLabel(row['custom_label'], row['shipping_method']), axis=1)
        df['zip'] = df['zip'].astype(str).str.extract(r'(\d{4})', expand=False)
        df['custom_label'] = df.apply(multiplyCustomLabel, axis=1)
        df['Quantity'] = 1

        '''
        =============   Kogan   =============
        '''
    elif platform == 'kogan':
        df['custom_label'] = df['custom_label'].astype(str).apply(lambda x: cleanCustomLabel(x))
        df['address'] = df['address1'] + ' ' + df['address2'].astype(str)
        df['shipping_method'] = df['amt'].astype(float).apply(lambda x: 'tracking' if x >= TRACKING_AMT else 'untracked')
        df['custom_label'] = df['custom_label'].str.lstrip('NEX-')
        df['custom_label'] = df['custom_label'].str.replace('[KG-','[')
        df['custom_label'] = df['custom_label'].str.replace('[USAMS-','[')
        df['custom_label'] = df['custom_label'].str.replace('[UB-','[')
        df['custom_label'] = df['custom_label'].str.replace(r'^\[KG\]/', '', regex=True)
        df['custom_label'] = df['custom_label'].astype(str).apply(lambda x: addPlatform(x, "KG"))
        df['custom_label'] = df.apply(lambda row: replaceLabel(row['custom_label'], " "), axis=1) #KG doesnt need shipping edit
        df['zip'] = df['zip'].astype(str).str.extract(r'(\d{4})', expand=False)
        df['custom_label'] = df.apply(multiplyCustomLabel, axis=1)
        df['Quantity'] = 1

        '''
        =============   Catch   =============
        '''
    elif platform == 'catch':
        df['custom_label'] = df['custom_label'].astype(str).apply(lambda x: cleanCustomLabel(x))
        df['address'] = df['company'] + ' ' + df['address1'].fillna('') + ' ' + df['address2']
        df['rname'] = df['fname'] + ' ' + df['lname']
        df['shipping_method'] = df['amt'].astype(float).apply(lambda x: 'tracking' if x >= TRACKING_AMT else 'untracked')
        df['custom_label'] = df['custom_label'].str.replace(r'^\[C\]/', '', regex=True)
        df['custom_label'] = df['custom_label'].astype(str).apply(lambda x: addPlatform(x, "C"))
        df['custom_label'] = df.apply(lambda row: replaceLabel(row['custom_label'], row['shipping_method']), axis=1)
        df['zip'] = df['zip'].astype(str).str.extract(r'(\d{4})', expand=False)
        df['custom_label'] = df.apply(multiplyCustomLabel, axis=1)
        df['Quantity'] = 1

    #finishing up
    df['address'] = df['address'].str.strip()
    if 'rname' in df.columns:
        df['rname'] = df['rname'].str.strip()
    df.reset_index(drop=True, inplace=True)
    return df

def read_and_standardize(directory):
    all_data = []

    # Iterate through files in the directory
    for filename in os.listdir(directory):
        if '_orders.csv' in filename.lower():
            platform = filename.split('_')[0].lower()  # Extract platform name
            filepath = os.path.join(directory, filename)
            print("----------------------------------------------------------------")
            print(f"Processing file: {filename}, Detected platform: {platform}")
            df = process_file(filepath, platform)
            
            # Skip empty DataFrames
            if not df.empty:
                df['source_platform'] = platform  # Add a column to identify the source
                all_data.append(df)
            
            print("================================================================")

    # Combine all data into a single DataFrame
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True, sort=False)
    else:
        combined_df = pd.DataFrame()  # Return an empty DataFrame if no data

    return combined_df

# Set the directory containing the CSV files
csv_directory = os.getcwd()  # Current directory

# Read and standardize all files
standardized_df = read_and_standardize(csv_directory)

# After the standardized DataFrame is created
standardized_df.to_csv('standardized_columns.csv', index=False)  # Save to a CSV file
# print(standardized_df.head())  # Print the first few rows of the DataFrame
