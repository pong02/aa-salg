import csv
import os
import sys
import re

def migrate_csv(target_csv, changes_csv="sdCodeChanges.csv"):
    # Load replacements from changes CSV
    replacements = []
    with open(changes_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not {"NEW", "OLD"}.issubset(reader.fieldnames):
            raise ValueError("sdCodeChanges.csv must have headers: NEW, OLD")
        for row in reader:
            old, new = row["OLD"], row["NEW"]
            if old and new:
                pattern = re.compile(re.escape(old), re.IGNORECASE)
                replacements.append((pattern, new))

    # Sort longest OLD first to avoid partial overlaps
    replacements.sort(key=lambda x: -len(x[0].pattern))

    # Construct output filename
    base, ext = os.path.splitext(target_csv)
    output_csv = f"{base}_migrated{ext}"

    # Process the target CSV
    with open(target_csv, newline="", encoding="utf-8") as infile, \
         open(output_csv, "w", newline="", encoding="utf-8") as outfile:
        
        reader = csv.reader(infile)
        writer = csv.writer(outfile)

        for row in reader:
            new_row = []
            for cell in row:
                items = [item.strip() for item in cell.split(",")]
                updated_items = []
                for item in items:
                    for pattern, new in replacements:
                        if pattern.search(item):
                            item = pattern.sub(new, item)
                            break  # stop after first replacement for this item
                    updated_items.append(item)
                new_row.append(", ".join(updated_items))
            writer.writerow(new_row)

    print(f"Migrated CSV written to: {output_csv}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python migrate_csv.py <target_csv> [changes_csv]")
    else:
        target_csv = sys.argv[1]
        changes_csv = sys.argv[2] if len(sys.argv) > 2 else "sdCodeChanges.csv"
        migrate_csv(target_csv, changes_csv)
