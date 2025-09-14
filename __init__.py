import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # headless backend for Windows
from .computation_engine import run_pipeline as original_run_pipeline, conn

# Base paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(BASE_DIR, "static", "reports")
CHART_DIR  = os.path.join(BASE_DIR, "static", "charts")
os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(CHART_DIR, exist_ok=True)

def run_pipeline_on_uploaded_csv(csv_path: str):
    """
    Runs computation pipeline on uploaded CSV.
    Saves processed CSV, Excel, PDF, charts for frontend access.
    Returns dict with file paths and alerts.
    """
    try:
        df = original_run_pipeline(csv_path)
    except KeyError as e:
        # CSV missing expected columns
        raise Exception(f"CSV is missing required column: {e}")

    # Save reports
    csv_file = os.path.join(REPORT_DIR, "latest_processed.csv")
    excel_file = os.path.join(REPORT_DIR, "latest_processed.xlsx")
    pdf_file = os.path.join(REPORT_DIR, "latest_report.pdf")

    df.to_csv(csv_file, index=False)
    df.to_excel(excel_file, index=False)

    # Charts
    import matplotlib.pyplot as plt

    # Drift
    drift_chart = os.path.join(CHART_DIR, "drift.png")
    plt.figure()
    if "drift" in df.columns:
        df["drift"].plot(title="Drift Over Time")
    plt.savefig(drift_chart)
    plt.close()

    # RUL & Health
    rul_chart = os.path.join(CHART_DIR, "rul_health.png")
    plt.figure()
    cols = [c for c in ["rul_days", "health"] if c in df.columns]
    if cols:
        df[cols].plot(title="RUL & Health")
    plt.savefig(rul_chart)
    plt.close()

    # Alerts: latest row summary
    alerts = []
    for col in ["measured", "anomaly", "alert", "maintenance"]:
        if col not in df.columns:
            df[col] = None
    alerts = df[["measured", "anomaly", "alert", "maintenance"]].tail(1).to_dict(orient="records")

    return {
    "processed_csv": csv_file,
    "report_files": {"csv": csv_file, "excel": excel_file, "pdf": pdf_file},
    "alerts": alerts,
    "chart_files": {"drift": drift_chart, "rul_health": rul_chart}
    }



def get_history(limit: int = 200):
    """
    Returns last 'limit' rows from SQLite as pandas DataFrame
    """
    import sqlite3
    from .computation_engine import conn
    query = f"SELECT * FROM temperature_readings ORDER BY id DESC LIMIT {limit}"
    df = pd.read_sql_query(query, conn)
    return df.iloc[::-1].reset_index(drop=True)
