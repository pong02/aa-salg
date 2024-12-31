import pandas as pd

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
        })
        .reset_index()
    )

    # Rearrange columns to match the desired order
    column_order = ['id', 'rname', 'address', 'city', 'state', 'zip', 'custom_label', 'Quantity']
    merged_df = merged_df[column_order]

    # Save the merged DataFrame to the output CSV file
    merged_df.to_csv(output_csv, index=False)
    print(f"Merged data has been saved to: {output_csv}")


# Call the function with the output of the first part
input_csv = 'standardized_columns.csv'  # Input file from the first part
output_csv = 'merged_labels.csv'  # Output file after merging

merge_orders(input_csv, output_csv)
