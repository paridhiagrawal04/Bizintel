import json
import pandas as pd
import numpy as np
import sys
import os

# ═══════════════════════════════════════════════════════════
# COLUMN ROLE KEYWORDS
# WHY: Instead of hardcoding exact column names, we define
#      keyword families. Any column whose name CONTAINS one
#      of these keywords gets assigned that role.
#      e.g. "order_date", "transaction_date" both contain
#      "date" → assigned role "date"
# ═══════════════════════════════════════════════════════════
ROLE_KEYWORDS = {
    "date":     ["date", "time", "day", "month", "year", "period", "week"],
    "sales":    ["sales", "revenue", "amount", "total", "price", "income",
                 "earning", "turnover", "profit", "cost", "expense", "salary",
                 "wage", "payment", "charge", "fee", "spend"],
    "quantity": ["quantity", "qty", "units", "count", "volume", "stock",
                 "inventory", "shipment", "orders", "transactions"],
    "category": ["product", "item", "category", "type", "department", "dept",
                 "region", "city", "country", "location", "branch", "segment",
                 "gender", "status", "name", "employee", "customer", "channel"]
}


# ═══════════════════════════════════════════════════════════
# LOAD FILE
# ═══════════════════════════════════════════════════════════
def load_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".xlsx", ".xls"]:
        return pd.read_excel(file_path)
    elif ext == ".csv":
        return pd.read_csv(file_path)
    else:
        raise ValueError(f"Unsupported file type '{ext}'. Use .xlsx, .xls, or .csv")


# ═══════════════════════════════════════════════════════════
# STEP 1 — DETECT COLUMN ROLES
#
# WHY: We score every column against every role's keyword
#      list. The column with the highest score for a role
#      wins that role. This handles columns like
#      "Monthly_Revenue" (contains "revenue" → sales role)
#      without needing an exact match.
# ═══════════════════════════════════════════════════════════
def detect_column_roles(df):
    roles         = {}
    used_columns  = set()

    for role, keywords in ROLE_KEYWORDS.items():
        best_col   = None
        best_score = 0

        for col in df.columns:
            if col in used_columns:
                continue

            col_lower = col.lower().replace("_", " ").replace("-", " ")
            score     = sum(1 for kw in keywords if kw in col_lower)

            # Boost score using actual data type
            if role == "date":
                try:
                    pd.to_datetime(df[col].dropna().head(10), errors="raise")
                    score += 3
                except Exception:
                    pass

            elif role == "sales":
                if pd.api.types.is_numeric_dtype(df[col]):
                    score += 2

            elif role == "quantity":
                if pd.api.types.is_numeric_dtype(df[col]):
                    score += 1

            elif role == "category":
                if df[col].dtype == object:
                    unique_ratio = df[col].nunique() / max(len(df), 1)
                    if unique_ratio < 0.5:
                        score += 2

            if score > best_score:
                best_score = score
                best_col   = col

        if best_col and best_score > 0:
            roles[role] = best_col
            used_columns.add(best_col)

    return roles


# ═══════════════════════════════════════════════════════════
# STEP 2 — DETECT DATASET TYPE
# ═══════════════════════════════════════════════════════════
def detect_dataset_type(roles):
    if "date" in roles and "sales" in roles and "category" in roles:
        return "sales"
    elif "date" in roles and "sales" in roles:
        return "financial"
    elif "sales" in roles and "category" in roles:
        return "hr"
    else:
        return "generic"


# ═══════════════════════════════════════════════════════════
# STEP 3 — CLEAN DATA
# ═══════════════════════════════════════════════════════════
def clean_data(df, roles):
    for role in ["sales", "quantity"]:
        if role in roles:
            df[roles[role]] = pd.to_numeric(df[roles[role]], errors="coerce")

    if "date" in roles:
        df[roles["date"]] = pd.to_datetime(df[roles["date"]], errors="coerce")
        df = df.dropna(subset=[roles["date"]])

    if "sales" in roles:
        df = df.dropna(subset=[roles["sales"]])

    return df


# ═══════════════════════════════════════════════════════════
# STEP 4 — EDA SUMMARY
# WHY: Every analysis starts with understanding the data.
#      Returns shape, nulls, and descriptive stats.
#      Directly fulfils the EDA objective in synopsis.
# ═══════════════════════════════════════════════════════════
def eda_summary(df, roles):
    summary = {
        "total_rows":     int(df.shape[0]),
        "total_columns":  int(df.shape[1]),
        "columns":        list(df.columns),
        "detected_roles": {role: col for role, col in roles.items()},
        "null_counts":    {col: int(df[col].isna().sum()) for col in df.columns},
        "numeric_stats":  {}
    }

    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        summary["numeric_stats"][col] = {
            "mean":   round(float(df[col].mean()),   2),
            "median": round(float(df[col].median()), 2),
            "std":    round(float(df[col].std()),    2),
            "min":    round(float(df[col].min()),    2),
            "max":    round(float(df[col].max()),    2)
        }

    return summary


# ═══════════════════════════════════════════════════════════
# STEP 5 — ANOMALY DETECTION (Z-score method)
# WHY: Any point > 2 std deviations from the mean is unusual.
#      This is a genuine statistical technique — good for viva.
# ═══════════════════════════════════════════════════════════
def detect_anomalies(df, sales_col):
    mean = df[sales_col].mean()
    std  = df[sales_col].std()

    if std == 0:
        return []

    anomalies = df[np.abs(df[sales_col] - mean) > 2 * std]

    return [
        {
            "index":     int(i),
            "value":     round(float(row[sales_col]), 2),
            "deviation": round(float(abs(row[sales_col] - mean) / std), 2)
        }
        for i, row in anomalies.iterrows()
    ][:5]


# ═══════════════════════════════════════════════════════════
# STEP 6 — NATURAL LANGUAGE INSIGHTS
# ═══════════════════════════════════════════════════════════
def generate_insights(results, dataset_type):
    insights = []

    if dataset_type in ["sales", "financial"]:
        if results.get("top_category"):
            pct = results.get("top_category_pct", 0)
            insights.append(
                f"'{results['top_category']}' is your top performer, "
                f"contributing {pct:.1f}% of total revenue."
            )
        if results.get("lowest_category"):
            insights.append(
                f"'{results['lowest_category']}' is your weakest — "
                f"consider reviewing its strategy."
            )
        if results.get("growth_rate") is not None:
            g         = results["growth_rate"]
            direction = "grown" if g >= 0 else "declined"
            insights.append(
                f"Overall performance has {direction} by {abs(g):.1f}% "
                f"from first to latest period."
            )
        if results.get("anomaly_count", 0) > 0:
            insights.append(
                f"{results['anomaly_count']} unusual data point(s) detected — "
                f"possible data entry errors or exceptional events."
            )
        if results.get("peak_period"):
            insights.append(f"Peak period was {results['peak_period']}.")

    elif dataset_type == "hr":
        if results.get("top_category"):
            insights.append(
                f"'{results['top_category']}' has the highest total value "
                f"among all groups."
            )
        if results.get("avg_value") is not None:
            insights.append(
                f"The average value across all records is "
                f"{results['avg_value']:,.2f}."
            )

    else:
        insights.append(
            f"Dataset contains {results.get('total_rows', '?')} rows "
            f"across {results.get('total_columns', '?')} columns."
        )
        if results.get("top_category"):
            insights.append(
                f"'{results['top_category']}' is the most frequent category."
            )

    return insights


# ═══════════════════════════════════════════════════════════
# ANALYSIS RUNNERS
# ═══════════════════════════════════════════════════════════

def analyze_sales(df, roles):
    results      = {}
    sales_col    = roles["sales"]
    date_col     = roles["date"]
    category_col = roles["category"]

    results["total_sales"]   = round(float(df[sales_col].sum()),  2)
    results["average_sales"] = round(float(df[sales_col].mean()), 2)
    results["total_orders"]  = int(len(df))

    cat_sales = df.groupby(category_col)[sales_col].sum().sort_values(ascending=False)
    total     = cat_sales.sum()

    results["top_category"]     = str(cat_sales.idxmax())
    results["lowest_category"]  = str(cat_sales.idxmin())
    results["top_category_pct"] = round(float(cat_sales.max() / total * 100), 1)

    results["category_sales"] = [
        {"category": str(k), "sales": round(float(v), 2),
         "pct": round(float(v / total * 100), 1)}
        for k, v in cat_sales.items()
    ]

    date_range = (df[date_col].max() - df[date_col].min()).days
    if date_range > 60:
        df = df.copy()
        df["period"] = df[date_col].dt.to_period("M").astype(str)
        period_label = "monthly"
    else:
        df = df.copy()
        df["period"] = df[date_col].dt.date.astype(str)
        period_label = "daily"

    results["period_label"] = period_label

    time_series = (
        df.groupby("period")[sales_col]
        .sum().reset_index().sort_values("period")
    )

    results["sales_over_time"] = [
        {"period": str(r["period"]), "sales": round(float(r[sales_col]), 2)}
        for _, r in time_series.iterrows()
    ]

    # Growth rate — exclude partial last period
    if len(time_series) >= 3:
        period_counts = df.groupby("period").size()
        avg_count     = period_counts.mean()
        last_period   = time_series.iloc[-1]["period"]
        last_count    = period_counts.get(last_period, 0)
        ts_clean = time_series.iloc[:-1] if last_count < avg_count * 0.5 else time_series
    else:
        ts_clean = time_series

    if len(ts_clean) >= 2:
        first = float(ts_clean.iloc[0][sales_col])
        last  = float(ts_clean.iloc[-1][sales_col])
        results["growth_rate"] = round(((last - first) / first) * 100, 2) if first != 0 else 0
    else:
        results["growth_rate"] = 0

    if not time_series.empty:
        results["peak_period"]   = str(time_series.loc[time_series[sales_col].idxmax(), "period"])
        results["lowest_period"] = str(time_series.loc[time_series[sales_col].idxmin(), "period"])

    anomalies                = detect_anomalies(df, sales_col)
    results["anomalies"]     = anomalies
    results["anomaly_count"] = len(anomalies)

    return results


def analyze_financial(df, roles):
    results   = {}
    sales_col = roles["sales"]
    date_col  = roles["date"]

    results["total_sales"]   = round(float(df[sales_col].sum()),  2)
    results["average_sales"] = round(float(df[sales_col].mean()), 2)
    results["total_orders"]  = int(len(df))

    date_range = (df[date_col].max() - df[date_col].min()).days
    df = df.copy()
    if date_range > 60:
        df["period"] = df[date_col].dt.to_period("M").astype(str)
        period_label = "monthly"
    else:
        df["period"] = df[date_col].dt.date.astype(str)
        period_label = "daily"

    results["period_label"] = period_label

    time_series = (
        df.groupby("period")[sales_col]
        .sum().reset_index().sort_values("period")
    )

    results["sales_over_time"] = [
        {"period": str(r["period"]), "sales": round(float(r[sales_col]), 2)}
        for _, r in time_series.iterrows()
    ]

    anomalies                = detect_anomalies(df, sales_col)
    results["anomalies"]     = anomalies
    results["anomaly_count"] = len(anomalies)

    return results


def analyze_hr(df, roles):
    results      = {}
    sales_col    = roles["sales"]
    category_col = roles["category"]

    results["total_sales"]   = round(float(df[sales_col].sum()),  2)
    results["average_sales"] = round(float(df[sales_col].mean()), 2)
    results["avg_value"]     = round(float(df[sales_col].mean()), 2)
    results["total_orders"]  = int(len(df))

    cat_sales = df.groupby(category_col)[sales_col].sum().sort_values(ascending=False)
    total     = cat_sales.sum()

    results["top_category"]    = str(cat_sales.idxmax())
    results["lowest_category"] = str(cat_sales.idxmin())

    results["category_sales"] = [
        {"category": str(k), "sales": round(float(v), 2),
         "pct": round(float(v / total * 100), 1)}
        for k, v in cat_sales.items()
    ]

    anomalies                = detect_anomalies(df, sales_col)
    results["anomalies"]     = anomalies
    results["anomaly_count"] = len(anomalies)

    return results


def analyze_generic(df, roles):
    results      = {}
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols     = df.select_dtypes(include=["object"]).columns.tolist()

    results["total_orders"] = int(len(df))

    if numeric_cols:
        primary              = numeric_cols[0]
        results["total_sales"]   = round(float(df[primary].sum()),  2)
        results["average_sales"] = round(float(df[primary].mean()), 2)
        anomalies                = detect_anomalies(df, primary)
        results["anomalies"]     = anomalies
        results["anomaly_count"] = len(anomalies)

    if cat_cols:
        primary_cat = cat_cols[0]
        counts      = df[primary_cat].value_counts()
        results["top_category"] = str(counts.idxmax())
        results["category_sales"] = [
            {"category": str(k), "sales": int(v),
             "pct": round(v / len(df) * 100, 1)}
            for k, v in counts.items()
        ]

    return results


# ═══════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════
def analyze(file_path):
    df = load_file(file_path)

    if df.empty:
        raise ValueError("The uploaded file is empty.")

    roles = detect_column_roles(df)

    if not roles:
        raise ValueError(
            "Could not detect any recognisable columns. "
            "Ensure your file has labelled column headers."
        )

    df           = clean_data(df, roles)

    if df.empty:
        raise ValueError("No valid data rows remain after cleaning.")

    results      = eda_summary(df, roles)
    dataset_type = detect_dataset_type(roles)

    results["dataset_type"] = dataset_type

    if dataset_type == "sales":
        results.update(analyze_sales(df, roles))
    elif dataset_type == "financial":
        results.update(analyze_financial(df, roles))
    elif dataset_type == "hr":
        results.update(analyze_hr(df, roles))
    else:
        results.update(analyze_generic(df, roles))

    results["insights"] = generate_insights(results, dataset_type)

    return results


# ═══════════════════════════════════════════════════════════
# CLI ENTRY
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            raise ValueError("Usage: python analyze.py <file_path>")
        print(json.dumps(analyze(sys.argv[1]), indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)