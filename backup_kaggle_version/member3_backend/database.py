# Member 3 - Database setup (SQLite)
#
# Makes the file smartsupply.db with 4 tables and fills them from the Kaggle data:
#   products        - one row per product (name, category, price, stock)
#   sales           - daily sales history from the dataset
#   stock_movements - every stock IN (purchase) or OUT (sale) the user enters
#   forecasts       - predicted sales for the next 30 days (from Member 1)
#
# The dataset has no stock, so current_stock starts empty (NULL).
# The user enters stock on the Inventory page.
#
# Run once (after load_kaggle_data.py and forecast.py):  python database.py

import os
import sys
import sqlite3
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "smartsupply.db")
DATA_FOLDER = os.path.join(HERE, "..", "data")
FORECAST_FILE = os.path.join(HERE, "..", "member1_forecasting", "output", "forecast.csv")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # so we can read a row like row["name"]
    return conn


def create_database():
    products_file = os.path.join(DATA_FOLDER, "products.csv")
    if not os.path.exists(products_file):
        print("products.csv not found. Run data/load_kaggle_data.py first.")
        sys.exit(1)
    if not os.path.exists(FORECAST_FILE):
        print("forecast.csv not found. Run member1_forecasting/forecast.py first.")
        sys.exit(1)

    conn = get_connection()

    conn.executescript("""
    DROP TABLE IF EXISTS products;
    DROP TABLE IF EXISTS sales;
    DROP TABLE IF EXISTS stock_movements;
    DROP TABLE IF EXISTS forecasts;

    CREATE TABLE products (
        product_id     TEXT PRIMARY KEY,
        item_id        INTEGER,
        name           TEXT,
        category       TEXT,
        unit_price     REAL,
        current_stock  INTEGER
    );

    CREATE TABLE sales (
        date       TEXT,
        product_id TEXT REFERENCES products(product_id),
        quantity   INTEGER
    );

    CREATE TABLE stock_movements (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        date       TEXT,
        product_id TEXT REFERENCES products(product_id),
        type       TEXT CHECK (type IN ('IN', 'OUT')),
        quantity   INTEGER,
        note       TEXT
    );

    CREATE TABLE forecasts (
        product_id         TEXT REFERENCES products(product_id),
        date               TEXT,
        predicted_quantity INTEGER
    );
    """)

    # copy the CSV files into the tables (current_stock stays empty)
    products = pd.read_csv(products_file, encoding="utf-8")
    products.to_sql("products", conn, if_exists="append", index=False)

    sales = pd.read_csv(os.path.join(DATA_FOLDER, "sales.csv"))
    sales.to_sql("sales", conn, if_exists="append", index=False)

    forecasts = pd.read_csv(FORECAST_FILE)
    forecasts.to_sql("forecasts", conn, if_exists="append", index=False)

    conn.commit()
    conn.close()

    # print a few things so we can check the right data is loaded
    print("Database created:", DB_PATH)
    print("Products in database:", len(products))
    print("Sales from", sales["date"].min(), "to", sales["date"].max())


if __name__ == "__main__":
    create_database()
