## File: `services/dataset_append.py`

import os
import pandas as pd
from dotenv import load_dotenv
load_dotenv()
HISTORICAL_CSV_PATH = os.getenv("HISTORICAL_CSV_PATH","./data/historical_invoices.csv")
OUTPUT_CSV_PATH = os.getenv("OUTPUT_CSV_PATH","./data/invoice_anomaly_details.csv")


def load_historical_dataset():
    try:
        df = pd.read_csv(HISTORICAL_CSV_PATH)
        return df
    except Exception:
        return None


def append_to_csv(row: dict):
    df = None
    try:
        if os.path.exists(OUTPUT_CSV_PATH):
            df = pd.read_csv(OUTPUT_CSV_PATH)
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        else:
            df = pd.DataFrame([row])
        df.to_csv(OUTPUT_CSV_PATH, index=False)
    except Exception as e:
        print("dataset_append: failed to append", e)
