import json
import pandas as pd
import sys

# STEP 1 — Column mapping dictionary
COLUMN_MAPPINGS = {
    "date": ["date", "order_date", "day", "transaction_date"],
    
    "product": [
        "product",
        "item",
        "product_name",
        "item_name",
        "product category",
        "product_category"
    ],

    "sales": [
        "sales",
        "revenue",
        "amount",
        "total_sales",
        "total amount",
        "total_amount"
    ],

    "quantity": [
        "quantity",
        "units",
        "units_sold",
        "qty"
    ]
}

# STEP 2 — Function to standardize column names
def standardize_columns(df):
    new_columns = {}

    for standard_name, possible_names in COLUMN_MAPPINGS.items():
        for col in df.columns:
            if col.lower().strip() in possible_names:
                new_columns[col] = standard_name

    df = df.rename(columns=new_columns)
    return df


# STEP 3 — Get file path from Node.js / terminal
file_path = sys.argv[1]

# STEP 4 — Read Excel file
df = pd.read_excel(file_path)

# print("Original Columns:", df.columns)  

# STEP 5 — Standardize columns
df = standardize_columns(df)

# print("Standardized Columns:", df.columns)

# STEP 6 — Validate required columns
required_columns = ["date", "product", "sales"]

missing = [col for col in required_columns if col not in df.columns]

if missing:
    raise Exception(f"Missing required columns: {missing}")

# STEP 7 — Handle optional columns
if "quantity" not in df.columns:
    df["quantity"] = 1

# STEP 8 — Convert data types
df["sales"] = pd.to_numeric(df["sales"], errors="coerce")
df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")

# STEP 9 — Basic analysis
results = {}

results["\ntotal_sales"] = float(df["sales"].sum())
results["average_sales"] = float(df["sales"].mean())

if not df.empty:
    results["top_product"] = df.groupby("product")["sales"].sum().idxmax()
else:
    results["top_product"] = None

print(json.dumps(results))
