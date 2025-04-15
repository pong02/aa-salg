import pandas as pd
import re
from collections import defaultdict

def has_two_hyphens(s):
    return str(s).count('-') >= 2


def removePlatform(input_string):
    """
    Removes everything before and including the first '/' in the input string.
    """
    return re.sub(r'^.*?/', '', input_string)

def parseLabelCounts(label):
    """
    Parses a custom_label string to count occurrences of types in the second bracket,
    and sums the multipliers after '*' for each type.

    Parameters:
        label (str): The input custom_label string.

    Returns:
        dict: A dictionary with the content of the second bracket as keys and their summed multipliers as values.
    """
    # Initialize the dictionary to store counts of each type
    counts = defaultdict(int)
    
    # Step 1: Remove spaces and standardize separators
    label = label.replace(' ', '').replace(',[', '|[')

    # Step 2: Split the label by '|', which now separates each individual label
    parts = label.split('|')

    # Step 3: Process each part of the label
    for part in parts:
        # Remove everything before and including the first '/'
        part = removePlatform(part)

        # Extract the second bracket content
        match_bracket = re.search(r'\[(.*?)\]', part)
        if match_bracket:
            type_content = match_bracket.group(1)
            
            # Ensure the type is in the dictionary with an initial value of 0
            if type_content not in counts:
                counts[type_content] = 0
            
            # Find all multipliers in the part and sum them
            multipliers = re.findall(r'\*(\d+)', part)
            total_multiplier = sum(int(m) for m in multipliers) if multipliers else 1

            # Add the total multiplier to the type content's count
            counts[type_content] += total_multiplier
    
    return dict(counts)

def mergePackaging(packagingDict):
    """
    Calculate the most suitable envelope size based on total capacity in small-equivalents.

    Parameters:
        envelope_counts (dict): A dictionary with envelope types as keys and their counts as values.

    Returns:
        str: The most suitable envelope size.
    """

    ## why process when only 1 item
    if len(packagingDict) == 1:  # Check if dictionary length is 1
        key, value = list(packagingDict.items())[0]  # Access the single key-value pair
        if int(value) == 1:
            return key
    
    # Capacity map: Define the minimum capacity threshold for each package type
    capacity_map = {
        'Small': 1,                  # Small = 1
        'C5': 3,                     # Minimum for C5
        'C4': 6,                     # Minimum for C4
        'Parcel-Medium': 18,         # Minimum for Parcel-Medium
        'Parcel-ExLarge': 36,        # Minimum for Parcel-ExLarge
    }
    capacity_map_tracked = {
        'TMP-Small': 1,              # Same as Small
        'TMP-C5': 3,                 # Same as C5
        'TMP-Large': 12,              # Minimum for C4
        'Parcel-Medium': 18,         # Same as Parcel-Medium
        'Parcel-ExLarge': 36,        # Same as Parcel-ExLarge
    }
    capacity_map_express = {
        'Express': 3,                # Same as C5
        'Parcel-Express': 9         # Minimum for Parcel-Express
    }
    capacity_map_all = {
        'small': 1,
        'c5': 3,
        'c4': 6,
        'parcel-medium': 18,
        'parcel-exlarge': 36,
        'tmp-small': 1,
        'tmp-c5': 3,
        'tmp-large': 12,
        'parcel-medium': 18,
        'parcel-exLarge': 36,
        'express': 3,
        'parcel-express': 36
    }

    cap_map = capacity_map
    #when we get an input, we multiply and get min capacity needed
    total_capacity = 0
    for envelope,number in packagingDict.items():
        if envelope == "?":
            return "?"
        try:
            total_capacity += capacity_map_all[envelope.lower()]*number
        except KeyError as e:
            return "Error:"+envelope
        if "Express" in envelope:
            cap_map = capacity_map_express
        elif "TMP" in envelope or "Parcel" in envelope:
            cap_map = capacity_map_tracked

    previous_envelope= ""
    for envelope,cap in cap_map.items():
        if total_capacity == cap:
            return envelope
        elif total_capacity > cap:
            previous_envelope = envelope
        elif total_capacity < cap:
            return previous_envelope
    return previous_envelope

def extractItems(label):
    cleaned_label = re.sub(r'\[.*?\]/\[.*?\]', '', label).replace(' ','').replace(',',', ')
    return cleaned_label.strip()

def isNormalDelivery(string):
    keywords = ['tmp','express','parcel']
    for keyword in keywords:
        if keyword in string.lower():
            return False
    return True

def dumbPackaging(items):
    cableList = read_cable_codes('cables.csv')
    # print(items)
    itemList = items.split(', ')
    count = 0
    itemListLength = 0
    for item in itemList:
        if '*' in item:
            # Split only if the expected delimiter is present
            itemName, quantity = item.split('*')
        else:
            # Provide default values when the split fails
            itemName, quantity = item, "1"  # Default quantity to 1

        itemListLength += int(quantity)
        if itemName in cableList:
            count += int(quantity)
    if count == itemListLength: # Only when ALL products are of cable type
        if count < 3:
            return "C5"
        elif count >= 3 and count <= 4:
            return "C4"
        elif count >= 5 and count <= 10:
            return "Parcel-Medium"
        else:
            "Parcel-ExLarge"
    else:
        # print("fall back to smart")
        return None
    
def smartPackaging(label):
    match = re.search(r'\[(.*?)\]', label)
    platform = match.group(1) if match else '?' 
    allPackaging = parseLabelCounts(label)
    allItems = extractItems(label)
    finalPackaging = mergePackaging(allPackaging)
    hardPackaging = dumbPackaging(allItems)
    if (hardPackaging != None and isNormalDelivery(finalPackaging)):
        # override smart packaging for cables
        finalPackaging = hardPackaging
    
    return "["+platform+"]/["+finalPackaging+"]"+allItems

def finishUpLabel(label):
    label = label.replace(' ', '').replace(',', ', ').replace('*', ' *')
    
    # Add a space after ] if followed by an alphabet
    label = re.sub(r'\](?=[A-Za-z])', '] ', label)

    return label.strip()

def read_cable_codes(file_path):
    df = pd.read_csv(file_path)
    data_array = df.iloc[:, 0].tolist()
    return data_array

def fill_missing_details(df):
    """
    Fills missing details for rows without an address or rname by propagating
    values from the row above within the same group, but only if they share the same id.
    """
    # Reset the index to ensure sequential row processing
    df = df.reset_index(drop=True)

    # Iterate over rows to ensure propagation happens only when IDs match
    for i in range(1, len(df)):
        if pd.isna(df.loc[i, 'address']) or df.loc[i, 'address'] == '':
            if df.loc[i, 'id'] == df.loc[i - 1, 'id']:  # Check if the IDs are the same
                df.loc[i, 'address'] = df.loc[i - 1, 'address']
                df.loc[i, 'rname'] = df.loc[i - 1, 'rname']
                df.loc[i, 'city'] = df.loc[i - 1, 'city']
                df.loc[i, 'zip'] = df.loc[i - 1, 'zip']
                df.loc[i, 'state'] = df.loc[i - 1, 'state']
    return df

def is_ebay_style_id(id_str):
    return bool(re.match(r'^\d{2}-\d{5}-\d{5}$', str(id_str)))

def nullify_summary_parent(group):
    id_str = str(group['id'].iloc[0])
    if is_ebay_style_id(id_str) and len(group) > 1:
        max_amt_idx = group['amt'].idxmax()
        group.loc[max_amt_idx, 'amt'] = 0
        group.loc[max_amt_idx, 'Quantity'] = 0
    return group

def merge_orders(input_csv, output_csv):
    """
    Reads the standardized CSV file, fills missing details, merges rows based on the merging rules,
    and saves the result to a new CSV.

    Parameters:
        input_csv (str): The input CSV file path.
        output_csv (str): The output CSV file path.
    """
    # Read the standardized CSV file
    df = pd.read_csv(input_csv)

    # Clean whitespace in key columns
    df['address'] = df['address'].str.strip()
    df['custom_label'] = df['custom_label'].str.strip()
    df['id'] = df['id'].str.strip()
    df['rname'] = df['rname'].str.strip()

    # Handle missing details (eBay-style orders)
    df = (
        df.sort_values(['id', 'address'])
        .groupby(['source_platform'], group_keys=False)
        .apply(fill_missing_details)
    )

    df = df.groupby('id', group_keys=False).apply(nullify_summary_parent)

    # Merge logic:
    # Group by address, recipient (rname), and source_platform
    merged_df = (
        df.groupby(['address', 'rname', 'source_platform'], dropna=False)
        .agg({
            'id': lambda x: ', '.join(sorted(x.dropna().unique())),  # Combine unique IDs
            'custom_label': lambda x: ', '.join(sorted(x.dropna().unique())),  # Combine custom labels
            'city': 'first',  # Keep the first city
            'zip': 'first',  # Keep the first zip
            'state': 'first',  # Keep the first state
            'Quantity': 'sum',  # Sum the quantities
            'amt' : 'sum'
        })
        .reset_index()
    )

    # Smart Packaging calculation
    merged_df['custom_label'] = merged_df['custom_label'].astype(str).apply(lambda x: smartPackaging(x)) 
    
    # Final touches to make label readable
    merged_df['custom_label'] = merged_df['custom_label'].astype(str).apply(lambda x: finishUpLabel(x)) 

    # Rearrange columns to match the desired order
    column_order = ['id', 'rname', 'address', 'city', 'state', 'zip', 'custom_label', 'Quantity', 'amt']
    merged_df = merged_df[column_order]

    merged_df = merged_df.drop(columns=['Quantity'])

    # Prepare for Sorting with custom order
    merged_df['sort'] = merged_df['custom_label'].str.split(']').str[-1].str.replace(" ", "", regex=True)
    merged_df['sort'] = merged_df['sort'].fillna("???").replace("", "???")

    # Apply sorting rules:
    # - Items with at least two '-' are sorted alphabetically.
    # - Items without at least two '-' (including empty strings or NaNs) are placed at the end.
    merged_df['sort_key'] = merged_df['sort'].apply(lambda x: (0, x) if has_two_hyphens(x) else (1, x))

    # Sort the DataFrame based on the defined sort key
    merged_df = merged_df.sort_values(by='sort_key')

    # Drop the temporary sorting key column
    merged_df = merged_df.drop(columns=['sort_key'])

    # Save the merged DataFrame to the output CSV file
    merged_df.to_csv(output_csv, index=False)
    print(f"Merged data has been saved to: {output_csv}")


# Call the function with the output of the first part
input_csv = 'standardized_columns.csv'  # Input file from the first part
output_csv = 'merged_labels.csv'  # Output file after merging

merge_orders(input_csv, output_csv)
