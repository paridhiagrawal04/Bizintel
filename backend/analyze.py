import json
import pandas as pd
import sys
import os

# ─────────────────────────────────────────────
# STEP 1 — Column mapping dictionary
# WHY: Different datasets use different names for the same concept.
#      We normalise everything to a single standard name so the rest
#      of the script never has to worry about variations.
# ─────────────────────────────────────────────
COLUMN_MAPPINGS = {
    "date": ["date", "order_date", "day", "transaction_date"],
    "product": [
        "product", "item", "product_name", "item_name",
        "product category", "product_category"
    ],
    "sales": [
        "sales", "revenue", "amount", "total_sales",
        "total amount", "total_amount"
    ],
    "quantity": ["quantity", "units", "units_sold", "qty"]
}


# ─────────────────────────────────────────────
# STEP 2 — Standardise column names
# WHY: A generic rename pass so every downstream function
#      can safely assume columns are called "date", "product", etc.
# ─────────────────────────────────────────────
def standardize_columns(df):
    new_columns = {}
    for standard_name, possible_names in COLUMN_MAPPINGS.items():
        for col in df.columns:
            if col.lower().strip() in possible_names:
                new_columns[col] = standard_name
    return df.rename(columns=new_columns)


# ─────────────────────────────────────────────
# STEP 3 — Load file (Excel OR CSV)
# WHY: Multer saves the original extension; we inspect it to pick
#      the right pandas reader instead of blindly calling read_excel.
# ─────────────────────────────────────────────
def load_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".xlsx", ".xls"]:
        return pd.read_excel(file_path)
    elif ext == ".csv":
        return pd.read_csv(file_path)
    else:
        raise ValueError(f"Unsupported file type: '{ext}'. Please upload .xlsx, .xls, or .csv")


# ─────────────────────────────────────────────
# STEP 4 — Generate natural-language insights
# WHY: Raw numbers are hard to interpret quickly. A one-sentence
#      summary (like a mini analyst note) is far more useful for a
#      small-business owner who is not a data expert.
# ─────────────────────────────────────────────
def generate_insights(df, results):
    insights = []

    # — Top product contribution —
    if results.get("top_product"):
        product_sales = df.groupby("product")["sales"].sum()
        top = results["top_product"]
        top_pct = (product_sales[top] / product_sales.sum()) * 100
        insights.append(
            f"'{top}' is your top performer, contributing "
            f"{top_pct:.1f}% of total revenue."
        )

    # — Lowest product —
    if results.get("lowest_product"):
        insights.append(
            f"'{results['lowest_product']}' is your weakest product "
            f"— consider reviewing its pricing or marketing."
        )

    # — Sales growth rate (first vs last period) —
    if "sales_over_time" in results and len(results["sales_over_time"]) >= 2:
        timeline = results["sales_over_time"]
        first_val = timeline[0]["sales"]
        last_val  = timeline[-1]["sales"]
        if first_val > 0:
            growth = ((last_val - first_val) / first_val) * 100
            direction = "increased" if growth >= 0 else "decreased"
            insights.append(
                f"Sales have {direction} by {abs(growth):.1f}% "
                f"from the first to the latest period."
            )

    # — Peak period —
    if results.get("peak_period"):
        insights.append(
            f"Your peak sales period was {results['peak_period']}."
        )

    return insights


# ─────────────────────────────────────────────
# STEP 5 — Main analysis function
# WHY: Keeping all logic in one function makes it easy to test
#      each part in isolation and avoids polluting global scope.
# ─────────────────────────────────────────────
def analyze(file_path):

    # 5a — Load
    df = load_file(file_path)

    # 5b — Standardise column names
    df = standardize_columns(df)

    # 5c — Validate required columns
    required = ["date", "product", "sales"]
    missing  = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. "
                         f"Found columns: {list(df.columns)}")

    # 5d — Optional quantity column
    if "quantity" not in df.columns:
        df["quantity"] = 1

    # 5e — Coerce numeric types
    #      errors="coerce" turns unparseable values into NaN
    #      (instead of crashing), so bad rows are dropped cleanly below.
    df["sales"]    = pd.to_numeric(df["sales"],    errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["date"]     = pd.to_datetime(df["date"],    errors="coerce")

    # 5f — Drop rows where critical values are missing
    df = df.dropna(subset=["sales", "date"])

    if df.empty:
        raise ValueError("No valid data rows found after cleaning.")

    # ── Core metrics ──────────────────────────────────────────────
    results = {}

    results["total_sales"]   = round(float(df["sales"].sum()), 2)
    results["average_sales"] = round(float(df["sales"].mean()), 2)
    results["total_orders"]  = int(len(df))

    # ── Product-level metrics ─────────────────────────────────────
    product_sales = df.groupby("product")["sales"].sum().sort_values(ascending=False)

    results["top_product"]    = str(product_sales.idxmax())
    results["lowest_product"] = str(product_sales.idxmin())

    # Chart data: product-wise sales (bar chart)
    # WHY: We return a list of {product, sales} objects so the
    #      frontend can feed them directly into Chart.js without
    #      any extra transformation.
    results["product_sales"] = [
        {"product": str(p), "sales": round(float(s), 2)}
        for p, s in product_sales.items()
    ]

    # ── Time-series metrics ───────────────────────────────────────
    # Decide granularity: if the data spans > 60 days use monthly,
    # otherwise use daily — avoids a chart with hundreds of data points.
    date_range = (df["date"].max() - df["date"].min()).days

    if date_range > 60:
        df["period"] = df["date"].dt.to_period("M").astype(str)
        period_label = "monthly"
    else:
        df["period"] = df["date"].dt.date.astype(str)
        period_label = "daily"

    sales_over_time = (
        df.groupby("period")["sales"]
        .sum()
        .reset_index()
        .sort_values("period")
    )

    results["period_label"] = period_label

    # Chart data: sales over time (line chart)
    results["sales_over_time"] = [
        {"period": str(row["period"]), "sales": round(float(row["sales"]), 2)}
        for _, row in sales_over_time.iterrows()
    ]

    # ── Peak & low periods ────────────────────────────────────────
    peak_idx  = sales_over_time["sales"].idxmax()
    low_idx   = sales_over_time["sales"].idxmin()

    results["peak_period"]   = str(sales_over_time.loc[peak_idx,  "period"])
    results["lowest_period"] = str(sales_over_time.loc[low_idx,   "period"])

    # ── Growth rate (first → last period) ────────────────────────
    if len(sales_over_time) >= 2:
        first = float(sales_over_time.iloc[0]["sales"])
        last  = float(sales_over_time.iloc[-1]["sales"])
        results["growth_rate"] = round(((last - first) / first) * 100, 2) if first != 0 else 0
    else:
        results["growth_rate"] = 0

    # ── Natural language insights ─────────────────────────────────
    results["insights"] = generate_insights(df, results)

    return results


# ─────────────────────────────────────────────
# STEP 6 — Entry point
# WHY: Wrapping execution in try/except means we ALWAYS output
#      valid JSON — either results or an {"error": "..."} object.
#      Node.js can then safely call JSON.parse(stdout) without
#      crashing on unexpected text.
# ─────────────────────────────────────────────
if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            raise ValueError("No file path provided.")

        file_path = sys.argv[1]
        results   = analyze(file_path)
        print(json.dumps(results))

    except Exception as e:
        # Print a structured error so Node.js knows what went wrong
        print(json.dumps({"error": str(e)}))
        sys.exit(1)