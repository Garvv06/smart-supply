# SmartSupply AI — Inventory Management and Demand Forecasting

A web app that predicts product demand for the next 30 days, gives reorder alerts,
and answers questions about products using a document assistant (RAG).

**All data comes from a real public dataset** — Kaggle "Predict Future Sales"
(1C Company, a Russian chain selling electronics, games, software and movies,
daily sales from Jan 2013 to Oct 2015, about 60 shops).

---

## Step 1: Get the dataset

1. Make a free Kaggle account.
2. Open https://www.kaggle.com/c/competitive-data-science-predict-future-sales/data
3. Click **Join Competition / I Understand and Accept**, then **Download All**.
4. Put the downloaded zip (or the csv files) inside the folder `data\kaggle`.
   The script unzips it and finds the files by itself.

## Step 2: Run (Windows, double-click in this order)

| File | What it does |
|---|---|
| `0_install_once.bat` | installs Python packages (first time only) |
| `1_load_kaggle_data.bat` | loads the dataset, trains the models, makes the database |
| `2_start_backend.bat` | starts the backend (keep it open) |
| `3_start_frontend.bat` | starts the website, the browser opens by itself (keep it open) |

### Or run step by step in Command Prompt

```
python -m pip install -r requirements.txt
python data\load_kaggle_data.py
python member1_forecasting\forecast.py
python member2_rag\rag.py
python member3_backend\database.py

cd member3_backend
python -m uvicorn app:app --port 8000
```
In a second Command Prompt:
```
cd member4_frontend
npm install
npm run dev
```
Open **http://localhost:5173**. API test page: **http://localhost:8000/docs**

---

## What comes from the dataset and what does not

| From the dataset | Not in the dataset |
|---|---|
| Product names (real names, many are in Russian) | Current stock — **entered by the user** on the Inventory page |
| Categories (main part translated to English) | Safety days and supplier lead time — **store settings** in `forecast.py` (7 days each, can be changed) |
| Prices (median selling price, in roubles) | |
| Daily units sold (all shops added together) | |

Nothing is made up. Until stock is entered, a product shows **"Stock not entered"**
and the suggested order is the stock needed for the next 30 days.

---

## Project structure

```
smartsupply-ai/
├── data/
│   ├── kaggle/                put the Kaggle download here
│   ├── load_kaggle_data.py    makes products.csv, sales.csv and the product reports
│   └── documents/             product reports + store summary (made from the dataset)
├── member1_forecasting/       MEMBER 1 – ML forecasting + reorder logic
├── member2_rag/               MEMBER 2 – document assistant (RAG)
├── member3_backend/           MEMBER 3 – database + API
└── member4_frontend/          MEMBER 4 – React website
```

```
Kaggle dataset -> load_kaggle_data.py -> Member 1 (forecast.py) ─┐
                                      -> Member 2 (rag.py) ──────┼──> Member 3 (API + SQLite) ──> Member 4 (website)
```

---

## Data preparation (`data/load_kaggle_data.py`)

1. Reads `sales_train.csv`, `items.csv`, `item_categories.csv`.
2. Removes rows that are not stock items (delivery charges, service items, tickets, the carry bag).
3. Adds up all shops so it works like one big store.
4. Picks the **20 best-selling items of the last year** that were already selling a year before (so the model has history).
5. Writes daily sales with 0 on days with no sale. Negative numbers (returns) become 0.
6. Writes one **product report** per product and one **store summary** — every number is calculated from the dataset.

## Member 1 — Demand Forecasting (`forecast.py`)

1. Features from the date: `day_number` (trend), `day_of_week`, `month` (one-hot encoded).
2. Last **60 days kept for testing**, train on the rest.
3. **Linear Regression** and **Random Forest**, compared with a **baseline** (average of last 30 days).
4. Error measured with **MAE** (average units per day the prediction is off by).
5. Better model is retrained on all data and predicts the **next 30 days**.
6. Reorder rules:
   - Safety stock = 7 days of average predicted sales
   - Reorder point = average daily sales × lead time (7 days) + safety stock
   - Stock ≤ reorder point → **Reorder Now**; ≤ 1.5 × reorder point → **Low**; else **OK**
   - Suggested order = next 30 days demand + safety stock − current stock

## Member 2 — RAG Document Assistant (`rag.py`)

1. **Load** all `.txt`/`.pdf` files in `data/documents` (dataset reports + anything uploaded).
2. **Chunk** into paragraphs.
3. **Embed** with **TF-IDF**.
4. **Retrieve** with **cosine similarity**, top 3 paragraphs.
5. **Answer** with the best paragraph and show the **source file**.
6. **Grounding check**: below 0.10 similarity it says "not found" instead of guessing.

**Evaluation:** for every product it asks "What is the price of …?" and "How many units of … were sold?"
and checks the right report is found. The accuracy is printed when you run `rag.py`.

## Member 3 — Backend + Database (`database.py`, `app.py`)

SQLite with 4 tables: `products`, `sales`, `stock_movements`, `forecasts`.

| Method | URL | Purpose |
|---|---|---|
| GET | /api/dashboard | summary numbers, charts, alerts |
| GET | /api/products | product list (filter by category) |
| GET | /api/reorder | stock status + suggested order |
| GET | /api/forecast/{id} | last 60 days + next 30 days |
| GET | /api/metrics | model accuracy |
| GET/POST | /api/movements | view / add stock IN or OUT |
| POST | /api/ask | ask the document assistant |
| POST | /api/upload | upload a new document |

## Member 4 — Frontend (`member4_frontend/src`)

- **Dashboard** — units sold, expected demand, alerts, monthly sales, units by category
- **Inventory** — enter stock (IN/OUT), product table with status and suggested order
- **Forecast** — actual vs forecast chart for any product, model accuracy chart
- **Document Assistant** — ask questions, see the source, upload documents

---

## Likely viva questions

- **Where does the data come from?** Kaggle "Predict Future Sales", real sales of 1C Company (2013–2015).
- **Why is stock entered by hand?** The dataset only has sales. Stock is what the store counts, so the user enters it.
- **Why compare with a baseline?** To prove ML actually helps over a simple average.
- **Why MAE?** Easy to explain: "on average we are off by X units per day."
- **Why test on the last 60 days?** In time series we must test on the future, never random past days.
- **Why TF-IDF?** Simple, fast, works offline, good for short documents.
- **How do you stop wrong answers in RAG?** Answers only come from the documents, the source is shown, and it says "not found" when nothing matches.
- **Does it order automatically?** No, it only suggests. The user decides.
