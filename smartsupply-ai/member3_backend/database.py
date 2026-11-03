# Member 3 - Database setup (SQLite)
#
# Makes the file smartsupply.db and fills it from the AdventureWorks data and Member 1's results:
#   products        - one row per product (category, price, supplier, lead time, stock, chosen model)
#   suppliers       - the suppliers of our products (credit rating, preferred or not)
#   sales           - daily online sales history from the dataset
#   purchase_orders - purchase order lines with our suppliers
#   stock_movements - every stock IN (purchase received) or OUT (sale):
#                     from the dataset, and the ones the user enters in the app
#   forecasts       - predicted sales for the next 30 days (from Member 1)
#   model_metrics   - error of each model for each product (from Member 1)
#
# Run once (after load_data.py and forecast.py):  python database.py
# Running it again starts the database fresh (movements entered in the app are removed).

import os
import sys
import sqlite3
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "smartsupply.db")
DATA_FOLDER = os.path.join(HERE, "..", "data")
OUTPUT_FOLDER = os.path.join(HERE, "..", "member1_forecasting", "output")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # so we can read a row like row["name"]
    return conn


def read_csv(folder, file_name, message):
    path = os.path.join(folder, file_name)
    if not os.path.exists(path):
        print(file_name, "not found.", message)
        sys.exit(1)
    return pd.read_csv(path, encoding="utf-8")


def create_database():
    products = read_csv(DATA_FOLDER, "products.csv", "Run data/load_data.py first.")
    suppliers = read_csv(DATA_FOLDER, "suppliers.csv", "Run data/load_data.py first.")
    sales = read_csv(DATA_FOLDER, "sales.csv", "Run data/load_data.py first.")
    purchase_orders = read_csv(DATA_FOLDER, "purchase_orders.csv", "Run data/load_data.py first.")
    movements = read_csv(DATA_FOLDER, "movements.csv", "Run data/load_data.py first.")
    forecasts = read_csv(OUTPUT_FOLDER, "forecast.csv", "Run member1_forecasting/forecast.py first.")
    metrics = read_csv(OUTPUT_FOLDER, "model_metrics.csv", "Run member1_forecasting/forecast.py first.")
    settings = read_csv(OUTPUT_FOLDER, "forecast_settings.csv", "Run member1_forecasting/forecast.py first.")

    # add the chosen model and its error to every product
    products = products.merge(settings, on="product_id", how="left")
    movements["source"] = "dataset"

    conn = get_connection()
    conn.executescript("""
    DROP TABLE IF EXISTS products;
    DROP TABLE IF EXISTS suppliers;
    DROP TABLE IF EXISTS sales;
    DROP TABLE IF EXISTS purchase_orders;
    DROP TABLE IF EXISTS stock_movements;
    DROP TABLE IF EXISTS forecasts;
    DROP TABLE IF EXISTS model_metrics;

    CREATE TABLE suppliers (
        supplier_id        INTEGER PRIMARY KEY,
        name               TEXT,
        account_number     TEXT,
        credit_rating      INTEGER,
        credit_rating_text TEXT,
        preferred          INTEGER,
        active             INTEGER
    );

    CREATE TABLE products (
        product_id         TEXT PRIMARY KEY,
        aw_product_id      INTEGER,
        name               TEXT,
        category           TEXT,
        product_group      TEXT,
        unit_price         REAL,
        unit_cost          REAL,
        supplier_id        INTEGER REFERENCES suppliers(supplier_id),
        supplier_price     REAL,
        lead_time_days     INTEGER,
        min_order_qty      INTEGER,
        max_order_qty      INTEGER,
        on_order_qty       INTEGER,
        current_stock      INTEGER,
        best_model         TEXT,
        forecast_mae       REAL,
        forecast_error_std REAL
    );

    CREATE TABLE sales (
        date       TEXT,
        product_id TEXT REFERENCES products(product_id),
        quantity   INTEGER
    );

    CREATE TABLE purchase_orders (
        po_id        INTEGER,
        order_date   TEXT,
        ship_date    TEXT,
        due_date     TEXT,
        status       TEXT,
        supplier_id  INTEGER REFERENCES suppliers(supplier_id),
        product_name TEXT,
        product_id   TEXT,
        order_qty    INTEGER,
        unit_price   REAL,
        received_qty INTEGER,
        rejected_qty INTEGER,
        line_total   REAL
    );

    CREATE TABLE stock_movements (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        date       TEXT,
        product_id TEXT REFERENCES products(product_id),
        type       TEXT CHECK (type IN ('IN', 'OUT')),
        quantity   INTEGER,
        note       TEXT,
        source     TEXT CHECK (source IN ('dataset', 'user'))
    );

    CREATE TABLE forecasts (
        product_id         TEXT REFERENCES products(product_id),
        date               TEXT,
        predicted_quantity REAL
    );

    CREATE TABLE model_metrics (
        product_id          TEXT REFERENCES products(product_id),
        model               TEXT,
        MAE                 REAL,
        MAE_percent         REAL,
        month_error_percent REAL,
        chosen              INTEGER
    );

    -- indexes make the searches by product fast
    CREATE INDEX idx_sales_product ON sales(product_id, date);
    CREATE INDEX idx_movements_product ON stock_movements(product_id, date);
    CREATE INDEX idx_forecasts_product ON forecasts(product_id, date);
    """)

    # copy the CSV files into the tables
    suppliers.to_sql("suppliers", conn, if_exists="append", index=False)
    products.to_sql("products", conn, if_exists="append", index=False)
    sales.to_sql("sales", conn, if_exists="append", index=False)
    purchase_orders.to_sql("purchase_orders", conn, if_exists="append", index=False)
    movements.to_sql("stock_movements", conn, if_exists="append", index=False)
    forecasts.to_sql("forecasts", conn, if_exists="append", index=False)
    metrics.to_sql("model_metrics", conn, if_exists="append", index=False)

    conn.commit()
    conn.close()

    # print a few things so we can check the right data is loaded
    print("Database created:", DB_PATH)
    print("Products:", len(products), "| suppliers:", len(suppliers),
          "| purchase order lines:", len(purchase_orders), "| stock movements:", len(movements))
    print("Sales from", sales["date"].min(), "to", sales["date"].max())


if __name__ == "__main__":
    create_database()
