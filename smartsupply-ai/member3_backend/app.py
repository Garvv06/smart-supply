# Member 3 - Backend API (FastAPI)
#
# This file connects everything:
#   - the database (products, sales, stock movements, forecasts)
#   - Member 1's reorder logic
#   - Member 2's document assistant
#   - Member 4's React website (it calls these URLs)
#
# APIs:
#   GET  /api/dashboard       summary numbers for the dashboard
#   GET  /api/products        all products (can filter by category)
#   GET  /api/reorder         stock status and suggested order quantity
#   GET  /api/forecast/{id}   last 60 days of sales + next 30 days forecast
#   GET  /api/metrics         error of each model
#   GET  /api/movements       last 50 stock IN / OUT entries
#   POST /api/movements       add a stock IN / OUT entry (updates the stock)
#   GET  /api/suppliers       suppliers with their credit rating
#   POST /api/ask             ask a question about the documents
#   POST /api/upload          upload a new document (saved in data/documents/uploads)
#   GET  /api/documents       list of documents
#
# Run:   python -m uvicorn app:app --reload --port 8000
# Test:  open http://localhost:8000/docs in the browser

import os
import sys
from datetime import date

import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import get_connection, DB_PATH, create_database

# So that we can import Member 1 and Member 2 files from their folders
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.append(os.path.join(ROOT, "member1_forecasting"))
sys.path.append(os.path.join(ROOT, "member2_rag"))

from forecast import reorder_suggestion                          # Member 1
from rag import DocumentAssistant, DOCS_FOLDER, list_documents   # Member 2

METRICS_FILE = os.path.join(ROOT, "member1_forecasting", "output", "model_metrics.csv")
UPLOADS_FOLDER = os.path.join(DOCS_FOLDER, "uploads")

# make the database if it is not there yet
if not os.path.exists(DB_PATH):
    create_database()

app = FastAPI(title="SmartSupply AI")

# The React app runs on a different port (5173), so we have to allow it
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# load the documents once when the server starts
assistant = DocumentAssistant()


def run_query(sql, params=()):
    # runs a SELECT query and gives back a list of dictionaries
    conn = get_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    result = []
    for row in rows:
        result.append(dict(row))
    return result


def get_reorder_list():
    # uses Member 1's reorder logic with the latest stock from the database
    products = run_query(
        "SELECT p.*, s.name AS supplier_name FROM products p "
        "LEFT JOIN suppliers s ON s.supplier_id = p.supplier_id")
    forecasts = pd.DataFrame(run_query("SELECT * FROM forecasts"))

    result = []
    for p in products:
        product_forecast = forecasts[forecasts["product_id"] == p["product_id"]]
        row = reorder_suggestion(p, product_forecast)
        row["category"] = p["category"]
        row["unit_price"] = p["unit_price"]
        row["supplier_name"] = p["supplier_name"]
        result.append(row)
    return result


# ---------- Dashboard ----------
@app.get("/api/dashboard")
def dashboard():
    products = run_query("SELECT * FROM products")
    reorder_list = get_reorder_list()

    reorder_now = 0
    low_stock = 0
    alerts = []
    for r in reorder_list:
        if r["status"] == "Reorder Now":
            reorder_now = reorder_now + 1
            alerts.append(r)
        if r["status"] == "Low":
            low_stock = low_stock + 1
            alerts.append(r)

    total_sold = run_query("SELECT SUM(quantity) AS total FROM sales")
    demand = run_query("SELECT SUM(predicted_quantity) AS total FROM forecasts")
    sales_by_category = run_query(
        "SELECT p.category, SUM(s.quantity) AS units FROM sales s "
        "JOIN products p ON p.product_id = s.product_id "
        "GROUP BY p.category ORDER BY units DESC")
    monthly_sales = run_query(
        "SELECT substr(date, 1, 7) AS month, SUM(quantity) AS quantity "
        "FROM sales GROUP BY month ORDER BY month")

    return {
        "total_products": len(products),
        "total_units_sold": total_sold[0]["total"],
        "expected_demand_30_days": demand[0]["total"],
        "reorder_now": reorder_now,
        "low_stock": low_stock,
        "alerts": alerts,
        "sales_by_category": sales_by_category,
        "monthly_sales": monthly_sales,
    }


# ---------- Products ----------
@app.get("/api/products")
def products(category: str = None):
    sql = "SELECT * FROM products"
    params = []
    if category:
        sql = sql + " WHERE category = ?"
        params.append(category)
    return run_query(sql, params)


@app.get("/api/reorder")
def reorder():
    return get_reorder_list()


@app.get("/api/suppliers")
def suppliers():
    return run_query("SELECT * FROM suppliers ORDER BY name")


# ---------- Forecast ----------
@app.get("/api/forecast/{product_id}")
def forecast(product_id: str):
    # last 60 days of sales (newest first, so we reverse it after)
    history = run_query(
        "SELECT date, quantity FROM sales WHERE product_id = ? ORDER BY date DESC LIMIT 60",
        (product_id,))
    history.reverse()

    future = run_query(
        "SELECT date, predicted_quantity FROM forecasts WHERE product_id = ? ORDER BY date",
        (product_id,))

    if len(history) == 0:
        raise HTTPException(404, "Product not found")

    return {"history": history, "forecast": future}


@app.get("/api/metrics")
def metrics():
    df = pd.read_csv(METRICS_FILE)
    average = df.groupby("model")["MAE"].mean().round(2).reset_index()
    return average.to_dict(orient="records")


# ---------- Stock movements ----------
class Movement(BaseModel):
    product_id: str
    type: str        # "IN" = purchase received, "OUT" = sold
    quantity: int
    note: str = ""


@app.get("/api/movements")
def movements():
    return run_query(
        "SELECT m.*, p.name FROM stock_movements m "
        "JOIN products p ON p.product_id = m.product_id "
        "ORDER BY m.id DESC LIMIT 50")


@app.post("/api/movements")
def add_movement(m: Movement):
    if m.type != "IN" and m.type != "OUT":
        raise HTTPException(400, "Type must be IN or OUT")
    if m.quantity <= 0:
        raise HTTPException(400, "Quantity must be more than 0")

    conn = get_connection()
    product = conn.execute("SELECT current_stock FROM products WHERE product_id = ?",
                           (m.product_id,)).fetchone()
    if product is None:
        conn.close()
        raise HTTPException(404, "Product not found")

    old_stock = product["current_stock"]
    if old_stock is None:
        old_stock = 0

    # IN adds to stock, OUT takes away from stock
    if m.type == "IN":
        new_stock = old_stock + m.quantity
    else:
        new_stock = old_stock - m.quantity

    if new_stock < 0:
        conn.close()
        raise HTTPException(400, "Not enough stock")

    conn.execute("INSERT INTO stock_movements (date, product_id, type, quantity, note, source) "
                 "VALUES (?, ?, ?, ?, ?, 'user')",
                 (date.today().isoformat(), m.product_id, m.type, m.quantity, m.note))
    conn.execute("UPDATE products SET current_stock = ? WHERE product_id = ?",
                 (new_stock, m.product_id))
    conn.commit()
    conn.close()
    return {"message": "Stock updated"}


# ---------- Document assistant ----------
class Question(BaseModel):
    question: str


@app.post("/api/ask")
def ask(q: Question):
    return assistant.ask(q.question)


@app.get("/api/documents")
def documents():
    # names like "contracts/contract_VERICELCORP.txt", so the user can see the kind of document
    return list_documents(DOCS_FOLDER)


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    file_name = os.path.basename(file.filename or "")
    if not (file_name.lower().endswith(".txt") or file_name.lower().endswith(".pdf")):
        raise HTTPException(400, "Only .txt and .pdf files are allowed")

    # uploads go in their own folder, so they cannot replace a document made from the dataset
    os.makedirs(UPLOADS_FOLDER, exist_ok=True)
    save_path = os.path.join(UPLOADS_FOLDER, file_name)
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    # read all documents again so the new file can be searched
    assistant.build_index()
    return {"message": file.filename + " uploaded", "chunks": len(assistant.chunks)}
