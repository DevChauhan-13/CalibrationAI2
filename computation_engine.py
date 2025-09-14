import os
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from sklearn.ensemble import IsolationForest
from matplotlib.backends.backend_pdf import PdfPages

# ---------------------------
# 1. Database setup
# ---------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "calibration.db")

REPORT_DIR = os.path.join(BASE_DIR, "static", "reports")
CHART_DIR = os.path.join(BASE_DIR, "static", "charts")

os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(CHART_DIR, exist_ok=True)


conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS temperature_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    measured REAL,
    ideal REAL,
    offset REAL,
    corrected REAL,
    anomaly TEXT,
    drift REAL,
    rul_days REAL,
    health REAL,
    alert TEXT,
    maintenance TEXT
)
""")
conn.commit()

# ---------------------------
# 2. Load CSV data
# ---------------------------
def load_csv(csv_path):
    return pd.read_csv(csv_path)

# ---------------------------
# 3. Compute offset & correction
# ---------------------------
def compute_correction(df):
    df["offset"] = df["measured"] - df["ideal"]
    df["corrected"] = df["measured"] - df["offset"]
    return df

# ---------------------------
# 4. Anomaly detection
# ---------------------------
def detect_anomalies(df, min_val=95, max_val=105, spike_threshold=2.0):
    anomalies = []
    
    values = df["measured"].values
    for i in range(len(values)):
        val = values[i]
        anomaly = None

        # Out-of-range
        if val < min_val or val > max_val:
            anomaly = "Out-of-Range"

        # Spike (sudden jump compared to previous)
        elif i > 0 and abs(val - values[i-1]) > spike_threshold:
            anomaly = "Spike"

        # Stuck value (3 repeats in a row)
        elif i >= 2 and values[i] == values[i-1] == values[i-2]:
            anomaly = "Stuck"

        # Erratic fluctuations (random up/down)
        elif i > 1 and ((val - values[i-1]) * (values[i-1] - values[i-2])) < 0:
            anomaly = "Noisy"

        anomalies.append(anomaly if anomaly else "Normal")

    df["anomaly"] = anomalies
    return df

# ---------------------------
# 5. Drift & RUL Prediction
# ---------------------------
def predict_drift_and_rul(df):
    df["drift"] = df["offset"].rolling(window=3, min_periods=1).mean()
    df["rul_days"] = np.maximum(0, 30 - df["drift"].abs()*10)
    df["health"] = np.clip(100 - df["drift"].abs()*20, 0, 100)
    return df

# ---------------------------
# 6. Alerts & Maintenance Suggestion
# ---------------------------
def assign_alerts_and_maintenance(df, min_val=95, max_val=105):
    alerts = []
    maint = []
    for _, row in df.iterrows():
        if row["measured"] < min_val or row["measured"] > max_val:
            alerts.append("CRITICAL")
        elif row["anomaly"] != "Normal":
            alerts.append("WARNING")
        else:
            alerts.append("NORMAL")

        if row["health"] < 50 or row["rul_days"] < 7:
            maint.append("Recalibrate within 1 week")
        elif row["health"] < 70:
            maint.append("Monitor closely, recalibrate soon")
        else:
            maint.append("No action needed")
    
    df["alert"] = alerts
    df["maintenance"] = maint
    return df

# ---------------------------
# 7. Store in SQLite
# ---------------------------
def save_to_db(df):
    for _, row in df.iterrows():
        cursor.execute("""
        INSERT INTO temperature_readings 
        (timestamp, measured, ideal, offset, corrected, anomaly, drift, rul_days, health, alert, maintenance)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            row["measured"], row["ideal"], row["offset"], row["corrected"],
            row["anomaly"], row["drift"], row["rul_days"], row["health"],
            row["alert"], row["maintenance"]
        ))
    conn.commit()

# ---------------------------
# 8. Report generation (CSV, Excel, PDF with charts & insights)
# ---------------------------
def generate_report(df, filename_prefix="latest_report"):
    csv_file = os.path.join(REPORT_DIR, f"{filename_prefix}.csv")
    excel_file = os.path.join(REPORT_DIR, f"{filename_prefix}.xlsx")
    pdf_file = os.path.join(REPORT_DIR, f"{filename_prefix}.pdf")
        # --- Also save charts as PNG for frontend ---
    plt.figure(figsize=(10,5))
    plt.plot(df.index, df["drift"], label="Drift")
    plt.title("Drift Over Time")
    plt.xlabel("Reading #")
    plt.ylabel("Drift")
    plt.legend()
    drift_png = os.path.join(CHART_DIR, "drift.png")
    plt.savefig(drift_png)
    plt.close()

    plt.figure(figsize=(10,5))
    plt.plot(df.index, df["rul_days"], label="RUL (days)")
    plt.plot(df.index, df["health"], label="Health (%)")
    plt.title("RUL & Health")
    plt.xlabel("Reading #")
    plt.ylabel("Value")
    plt.legend()
    rul_png = os.path.join(CHART_DIR, "rul_health.png")
    plt.savefig(rul_png)
    plt.close()

    print(f"✅ Charts saved to {CHART_DIR}")



    df.to_csv(csv_file, index=False)
    df.to_excel(excel_file, index=False)

    sns.set(style="whitegrid")
    with PdfPages(pdf_file) as pdf:
        # Table
        fig, ax = plt.subplots(figsize=(12,6))
        ax.axis("off")
        table = ax.table(
            cellText=df.head(20).values,
            colLabels=df.columns,
            loc="center"
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        pdf.savefig(fig)
        plt.close()

        # Drift
        plt.figure(figsize=(10,5))
        plt.plot(df.index, df["drift"], label="Drift")
        plt.title("Drift Over Time")
        plt.xlabel("Reading #")
        plt.ylabel("Drift")
        plt.legend()
        pdf.savefig()
        plt.close()

        # RUL / Health
        plt.figure(figsize=(10,5))
        plt.plot(df.index, df["rul_days"], label="RUL (days)")
        plt.plot(df.index, df["health"], label="Health (%)")
        plt.title("RUL & Health")
        plt.xlabel("Reading #")
        plt.ylabel("Value")
        plt.legend()
        pdf.savefig()
        plt.close()

        # Alerts summary
        plt.figure(figsize=(8,4))
        df["alert"].value_counts().plot(kind="bar", color=["green","orange","red"])
        plt.title("Alert Levels")
        pdf.savefig()
        plt.close()

        # Maintenance summary
        plt.figure(figsize=(8,4))
        df["maintenance"].value_counts().plot(kind="bar", color="skyblue")
        plt.title("Maintenance Suggestions")
        pdf.savefig()
        plt.close()

    print(f"✅ CSV saved: {csv_file}")
    print(f"✅ Excel saved: {excel_file}")
    print(f"✅ PDF report saved: {pdf_file}")

# ---------------------------
# 9. Full pipeline runner
# ---------------------------
def run_pipeline(csv_path):
    df = load_csv(csv_path)
    df = compute_correction(df)
    df = detect_anomalies(df)
    df = predict_drift_and_rul(df)
    df = assign_alerts_and_maintenance(df)
    save_to_db(df)
    generate_report(df)
    return df

# ---------------------------
# 10. Fetch history from DB
# ---------------------------
def get_history(limit=None):
    """
    Fetch stored readings from SQLite.
    :param limit: int -> number of most recent rows, or None for all.
    :return: pandas DataFrame
    """
    query = "SELECT * FROM temperature_readings ORDER BY id DESC"
    if limit:
        query += f" LIMIT {limit}"
    df = pd.read_sql_query(query, conn)
    return df.iloc[::-1].reset_index(drop=True)  # oldest → newest order
