# SmartSupply AI — Inventory Management and Demand Forecasting

A web app that predicts product demand for the next 30 days, warns before stock runs out,
suggests how much to reorder, and answers questions about business documents
(product reports, supplier profiles, purchase orders/invoices, supply contracts and the
inventory policy) with a document assistant (RAG) that always shows its sources.

**All data comes from two public datasets** (no account needed, `data/download_data.py` gets both):

| Dataset | What we use | Licence |
|---|---|---|
| [Microsoft AdventureWorks](https://github.com/microsoft/sql-server-samples/tree/master/samples/databases/adventure-works) — sample database of a bike company | products, suppliers, lead times, min/max order, stock counts, purchase orders, online sales, stock movements | MIT |
| [CUAD v1](https://huggingface.co/datasets/theatticusproject/cuad) — real contracts from SEC filings, labelled by lawyers | 24 supply agreements + the lawyers' answers, used as test questions | CC BY 4.0 |

---

## How to run (Windows, double-click in this order)

| File | What it does |
|---|---|
| `0_install_once.bat` | installs the Python packages (first time only) |
| `1_load_data.bat` | downloads the datasets, writes the documents, trains the models, tests the assistant, makes the database |
| `2_start_backend.bat` | starts the backend on http://localhost:8000 (keep it open) |
| `3_start_frontend.bat` | starts the website, the browser opens by itself (keep it open) |

### Or step by step (Windows, macOS or Linux)

```
python -m pip install -r requirements.txt
python data/download_data.py
python data/load_data.py
python member1_forecasting/forecast.py
python member2_rag/rag.py
python member3_backend/database.py

cd member3_backend
python -m uvicorn app:app --port 8000
```
In a second terminal:
```
cd member4_frontend
npm install
npm run dev
```
Open **http://localhost:5173**. API test page: **http://localhost:8000/docs**

The CSV files and documents made by `load_data.py` are already in the repository, so you can
skip `download_data.py` and `load_data.py` if you only want to run the app.

---

## Project structure

```
smartsupply-ai/
├── data/
│   ├── download_data.py       downloads AdventureWorks and CUAD (not saved in git)
│   ├── load_data.py           makes the CSV files, the documents and the test questions
│   ├── products.csv, suppliers.csv, sales.csv, purchase_orders.csv, movements.csv
│   ├── evaluation_questions.csv   222 test questions for the document assistant
│   └── documents/             products/ suppliers/ purchase_orders/ contracts/ policies/ uploads/
├── member1_forecasting/       MEMBER 1 – ML forecasting + reorder logic
├── member2_rag/               MEMBER 2 – document assistant (RAG) + its evaluation
├── member3_backend/           MEMBER 3 – SQLite database + FastAPI
└── member4_frontend/          MEMBER 4 – React website
```

```
AdventureWorks + CUAD -> load_data.py -> Member 1 (forecast.py) ─┐
                                       -> Member 2 (rag.py) ──────┼──> Member 3 (API + SQLite) ──> Member 4 (website)
```

---

## Data preparation (`data/load_data.py`)

1. Online sales only (orders customers placed on the website). Bike-shop orders stop early in the data.
2. Picks the **20 best-selling online products of the last year** that we buy from a supplier
   and that have at least 300 days of sales (so the model has history to train and test on).
3. Daily units sold per product, with 0 on days with no sale.
4. The sales from 2025-05-30 are removed: from that day every product suddenly has about half
   its usual sales (the sample data is not complete at the end). Training on them made every
   forecast too low: with them, the 30-day demand was 1,905 units and 2 products needed
   reordering; without them it is 3,570 units and 7 products.
5. Stock = latest stock count in the dataset. Units on order = purchase orders not yet due.
6. Writes one document per product, supplier and purchase order, 24 supply contracts from CUAD,
   a store summary, and the test questions (the right file and answer for each question).

## Member 1 — Demand Forecasting (`forecast.py`)

1. Features: `day_number` (trend), average of the last 7 and 28 days, same weekday last week,
   day of week (one-hot).
2. Models: **Linear Regression**, **Random Forest**, **Gradient Boosting**, and a
   **baseline** (average of the last 28 days).
3. Testing: we pretend it is 90, 60 and 30 days before the end, train on the days before, and
   predict the next 30 days one day at a time (3 test months, never random days).
4. Error measured with **MAE** (average units per day the prediction is off by).
5. Each product uses the model with the lowest error — **the baseline if no ML model beats it**.
   It is retrained on all data and predicts the **next 30 days**.
6. Reorder rules (also written in `data/documents/policies/inventory_policy.txt`):
   - Safety stock = 1.65 × forecast error (std) × √lead time  (95% service level)
   - Reorder point = average daily forecast × lead time + safety stock
   - Stock position = stock on hand + units on order
   - Position ≤ reorder point → **Reorder Now**; reaches it within 7 days → **Low**; else **OK**
   - Suggested order = demand for lead time + 30 days + safety stock − position,
     kept between the supplier's minimum and maximum order quantity

## Member 2 — RAG Document Assistant (`rag.py`)

1. **Load** every `.txt`/`.pdf` in `data/documents` and its subfolders (dataset documents + uploads).
2. **Chunk** into paragraphs (long contract paragraphs are cut at sentence ends, max 1500 characters).
3. **Embed** with **TF-IDF** (words and word pairs).
4. **Retrieve** with **cosine similarity**, top 3 paragraphs. A paragraph also gets half of the
   similarity of its document title, so the right document (contract name, PO number…) wins.
5. **Answer** with the best paragraph and show the **source file**. Optional: set `LLM_API_KEY`
   (any OpenAI-style API) and an LLM writes the answer using only those paragraphs.
6. **Grounding check**: below 0.10 similarity it says "not found" instead of guessing.

**Evaluation** (`python member2_rag/rag.py`, results in `member2_rag/output/`): the 222 questions in
`evaluation_questions.csv` — product price/supplier/lead time, supplier credit rating, purchase order
total, and 133 contract questions whose answers were marked by lawyers in CUAD.

| Group | Questions | Right file first | Right file in top 3 | Answer in the top 3 paragraphs |
|---|---|---|---|---|
| Products | 60 | 100% | 100% | 52% |
| Suppliers | 9 | 100% | 100% | 100% |
| Purchase orders | 20 | 100% | 100% | 100% |
| Contracts | 133 | 98% | 100% | 14% |
| **All** | **222** | **99%** | **100%** | **36%** |

TF-IDF finds the right document almost every time, but in long contracts it often picks the
wrong clause, because the question and the clause use different words ("governs" vs "governed by
the laws of"). Out-of-scope questions ("What is the weather today?") get "not found" 3 times out of 5,
and a question about a purchase order that does not exist gets the invoice of a different one.

## Forecast results

Average over the 20 products, testing on the last 3 months (`member1_forecasting/output/model_metrics.csv`):

| Model | MAE (units/day) | Error of the 30-day total | Products where it is best |
|---|---|---|---|
| Baseline (28-day average) | 1.95 | 11.1% | 13 |
| Linear Regression | 1.97 | 9.3% | 6 |
| Random Forest | 2.00 | 11.0% | 0 |
| Gradient Boosting | 2.16 | 14.4% | 1 |

The ML models are about as good as the baseline on daily error; Linear Regression is a little
better on the 30-day total, which is what ordering uses.

## Member 3 — Backend + Database (`database.py`, `app.py`)

SQLite with 7 tables: `products`, `suppliers`, `sales`, `purchase_orders`, `stock_movements`,
`forecasts`, `model_metrics`. Running `database.py` again starts the database fresh.

| Method | URL | Purpose |
|---|---|---|
| GET | /api/dashboard | summary numbers, charts, alerts |
| GET | /api/products | product list (filter by category) |
| GET | /api/suppliers | suppliers and their credit rating |
| GET | /api/reorder | stock status + suggested order (with supplier) |
| GET | /api/forecast/{id} | last 60 days + next 30 days |
| GET | /api/metrics | average error of each model |
| GET/POST | /api/movements | view / add stock IN or OUT |
| POST | /api/ask | ask the document assistant |
| GET | /api/documents | list of documents |
| POST | /api/upload | upload a .txt/.pdf (saved in `data/documents/uploads`) |

## Member 4 — Frontend (`member4_frontend/src`)

- **Dashboard** — units sold, expected demand, alerts, monthly sales, units by category
- **Inventory** — add stock IN/OUT, product table with supplier, stock, on order, status and
  suggested order, filters by category and supplier
- **Forecast** — actual vs forecast chart for any product, model accuracy chart
- **Document Assistant** — ask questions, see the source files, upload documents

---

## Likely viva questions

- **Where does the data come from?** Microsoft's AdventureWorks sample database (a made-up bike
  company, but full and consistent data) and real supply contracts from CUAD.
- **Why compare with a baseline?** To check that ML really helps. On this data the 28-day average
  is about as good as the ML models, so for many products the app uses the baseline — we report that honestly.
- **Why MAE?** Easy to explain: "on average we are off by X units per day."
- **Why test on the last 3 months?** In time series we must test on the future, never on random past days.
- **Why remove the last days of sales?** All products drop to about half on the same day, which is a
  gap in the sample data, not real demand.
- **Why TF-IDF?** Simple, fast, works offline, no API key. Its weak point is wording: it needs the same
  words as the document. Embeddings would fix this.
- **How do you stop wrong answers in RAG?** Answers only come from the documents, the source is shown,
  it says "not found" when nothing matches, and we measure how often the right answer is in the sources.
- **Does it order automatically?** No, it only suggests. A person checks and places the order.
