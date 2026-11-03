# This script loads the data for the whole project. All data comes from two public datasets
# (run download_data.py first, it downloads both):
#
# 1. Microsoft AdventureWorks sample database (MIT licence)
#    Official sample data published by Microsoft for "Adventure Works Cycles", a made-up bike company.
#    We use: products, suppliers (vendors), supplier lead times and order limits, stock counts,
#    purchase orders, online sales orders and stock movements.
#    https://github.com/microsoft/sql-server-samples/tree/master/samples/databases/adventure-works
#
# 2. CUAD - Contract Understanding Atticus Dataset (CC BY 4.0)
#    Real commercial contracts from public SEC filings, labelled by lawyers.
#    We use the supply agreements as the supplier contracts for the document assistant.
#    https://huggingface.co/datasets/theatticusproject/cuad
#
# What it makes:
#   products.csv         - the 20 best selling online products, with supplier, lead time and stock
#   suppliers.csv        - the suppliers of those products
#   sales.csv            - daily units sold online of each product
#   purchase_orders.csv  - purchase order lines with the suppliers
#   movements.csv        - stock movements from the dataset (IN = purchase received, OUT = sold)
#   evaluation_questions.csv - test questions for the document assistant (Member 2)
#   documents\           - product reports, supplier profiles, purchase orders, supply contracts
#                          and a store summary (used by the document assistant)
#
# Run:  python load_data.py

import os
import re
import sys
import csv
import json
import shutil
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
AW_FOLDER = os.path.join(HERE, "adventureworks")
CUAD_FILE = os.path.join(HERE, "cuad", "CUAD_v1.json")
DOCS_FOLDER = os.path.join(HERE, "documents")
NUMBER_OF_PRODUCTS = 20

# The AdventureWorks files have no header row, so we give the column names here.
# They are copied from the CREATE TABLE statements in Microsoft's install script (instawdb.sql).
COLUMNS = {
    "Product": ["ProductID", "Name", "ProductNumber", "MakeFlag", "FinishedGoodsFlag", "Color",
                "SafetyStockLevel", "ReorderPoint", "StandardCost", "ListPrice", "Size",
                "SizeUnitMeasureCode", "WeightUnitMeasureCode", "Weight", "DaysToManufacture",
                "ProductLine", "Class", "Style", "ProductSubcategoryID", "ProductModelID",
                "SellStartDate", "SellEndDate", "DiscontinuedDate", "rowguid", "ModifiedDate"],
    "ProductCategory": ["ProductCategoryID", "Name", "rowguid", "ModifiedDate"],
    "ProductSubcategory": ["ProductSubcategoryID", "ProductCategoryID", "Name", "rowguid", "ModifiedDate"],
    "ProductDescription": ["ProductDescriptionID", "Description", "rowguid", "ModifiedDate"],
    "ProductModelProductDescriptionCulture": ["ProductModelID", "ProductDescriptionID", "CultureID",
                                              "ModifiedDate"],
    "ProductInventory": ["ProductID", "LocationID", "Shelf", "Bin", "Quantity", "rowguid", "ModifiedDate"],
    "Location": ["LocationID", "Name", "CostRate", "Availability", "ModifiedDate"],
    "ProductVendor": ["ProductID", "BusinessEntityID", "AverageLeadTime", "StandardPrice",
                      "LastReceiptCost", "LastReceiptDate", "MinOrderQty", "MaxOrderQty",
                      "OnOrderQty", "UnitMeasureCode", "ModifiedDate"],
    "Vendor": ["BusinessEntityID", "AccountNumber", "Name", "CreditRating", "PreferredVendorStatus",
               "ActiveFlag", "PurchasingWebServiceURL", "ModifiedDate"],
    "ShipMethod": ["ShipMethodID", "Name", "ShipBase", "ShipRate", "rowguid", "ModifiedDate"],
    "PurchaseOrderHeader": ["PurchaseOrderID", "RevisionNumber", "Status", "EmployeeID", "VendorID",
                            "ShipMethodID", "OrderDate", "ShipDate", "SubTotal", "TaxAmt", "Freight",
                            "TotalDue", "ModifiedDate"],
    "PurchaseOrderDetail": ["PurchaseOrderID", "PurchaseOrderDetailID", "DueDate", "OrderQty",
                            "ProductID", "UnitPrice", "LineTotal", "ReceivedQty", "RejectedQty",
                            "StockedQty", "ModifiedDate"],
    "SalesOrderHeader": ["SalesOrderID", "RevisionNumber", "OrderDate", "DueDate", "ShipDate", "Status",
                         "OnlineOrderFlag", "SalesOrderNumber", "PurchaseOrderNumber", "AccountNumber",
                         "CustomerID", "SalesPersonID", "TerritoryID", "BillToAddressID",
                         "ShipToAddressID", "ShipMethodID", "CreditCardID", "CreditCardApprovalCode",
                         "CurrencyRateID", "SubTotal", "TaxAmt", "Freight", "TotalDue", "Comment",
                         "rowguid", "ModifiedDate"],
    "SalesOrderDetail": ["SalesOrderID", "SalesOrderDetailID", "CarrierTrackingNumber", "OrderQty",
                         "ProductID", "SpecialOfferID", "UnitPrice", "UnitPriceDiscount", "LineTotal",
                         "rowguid", "ModifiedDate"],
    "TransactionHistory": ["TransactionID", "ProductID", "ReferenceOrderID", "ReferenceOrderLineID",
                           "TransactionDate", "TransactionType", "Quantity", "ActualCost", "ModifiedDate"],
}
COLUMNS["TransactionHistoryArchive"] = COLUMNS["TransactionHistory"]

# Meanings of the codes, from the column descriptions in Microsoft's install script
CREDIT_RATINGS = {1: "Superior", 2: "Excellent", 3: "Above average", 4: "Average", 5: "Below average"}
PO_STATUS = {1: "Pending", 2: "Approved", 3: "Rejected", 4: "Complete"}

# Test questions for the supply contracts. The right answers were marked by lawyers in CUAD.
CONTRACT_QUESTIONS = {
    "Governing Law": "Which law governs the {name} supply agreement?",
    "Expiration Date": "When does the {name} supply agreement expire?",
    "Renewal Term": "How does the {name} supply agreement renew?",
    "Minimum Commitment": "What is the minimum purchase commitment in the {name} supply agreement?",
    "Warranty Duration": "How long is the warranty in the {name} supply agreement?",
    "Insurance": "What insurance is required by the {name} supply agreement?",
    "Audit Rights": "What audit rights are in the {name} supply agreement?",
    "Cap On Liability": "Is liability capped in the {name} supply agreement?",
}


def read_table(name):
    path = os.path.join(AW_FOLDER, name + ".csv")
    if not os.path.exists(path):
        print("ERROR: could not find", path)
        print("Run  python data\\download_data.py  first.")
        sys.exit(1)
    # tab separated, no header, no quotes around text
    return pd.read_csv(path, sep="\t", header=None, names=COLUMNS[name], encoding="utf-8",
                       quoting=csv.QUOTE_NONE, keep_default_na=False, na_values=[""])


def money(value):
    return "$" + format(float(value), ",.2f")


def write_text(folder, file_name, text):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, file_name), "w", encoding="utf-8") as f:
        f.write(text)


def clean_old_documents():
    # remove documents made by this script before (uploaded files are kept)
    for folder in ["products", "suppliers", "purchase_orders", "contracts"]:
        shutil.rmtree(os.path.join(DOCS_FOLDER, folder), ignore_errors=True)
    os.makedirs(DOCS_FOLDER, exist_ok=True)
    for file_name in os.listdir(DOCS_FOLDER):
        # product_P001.txt and store_summary.txt were made by the old version of the project
        if file_name.startswith("product_P") or file_name == "store_summary.txt":
            os.remove(os.path.join(DOCS_FOLDER, file_name))


def choose_supplier(vendor_rows):
    # Some products can be bought from 2 suppliers. We use the one with the
    # shortest lead time, then the preferred one, then the cheaper one.
    vendor_rows = vendor_rows.sort_values(["AverageLeadTime", "PreferredVendorStatus", "StandardPrice"],
                                          ascending=[True, False, True])
    return vendor_rows.iloc[0], vendor_rows.iloc[1:]


def write_product_report(product, item, other_suppliers, suppliers, stock_rows, item_daily):
    name = product["name"]
    text = "PRODUCT REPORT - " + name + "\n\n"
    text += ("Product ID: " + product["product_id"] + ". Product number in the dataset: "
             + item["ProductNumber"] + " (AdventureWorks product " + str(product["aw_product_id"])
             + "). Category: " + product["category"] + " (" + product["product_group"] + ").\n\n")
    if product["description"]:
        text += "Description of " + name + ": " + product["description"] + "\n\n"

    text += ("Price: " + name + " sells for " + money(product["unit_price"])
             + ". Its standard cost is " + money(product["unit_cost"]) + ".\n\n")

    supplier_name = suppliers[product["supplier_id"]]["name"]
    # rstrip so a name like "Trikes, Inc." does not get two dots
    text += ("Supplier: " + name + " is bought from " + supplier_name.rstrip(".") + ". The supplier's usual price is "
             + money(product["supplier_price"]) + " per unit. The lead time (days between ordering and "
             + "receiving) is " + str(product["lead_time_days"]) + " days. Each order must be between "
             + str(product["min_order_qty"]) + " and " + str(product["max_order_qty"]) + " units. "
             + str(product["on_order_qty"]) + " units are on order and have not arrived yet.\n\n")
    for index, other in other_suppliers.iterrows():
        text += ("Other supplier: " + name + " can also be bought from "
                 + suppliers[other["BusinessEntityID"]]["name"] + " for " + money(other["StandardPrice"])
                 + " per unit, with a lead time of " + str(int(other["AverageLeadTime"])) + " days.\n\n")

    places = []
    for index, row in stock_rows.iterrows():
        place = str(int(row["Quantity"])) + " units at " + row["LocationName"]
        if row["Shelf"] != "N/A":
            place += " (shelf " + str(row["Shelf"]) + ", bin " + str(row["Bin"]) + ")"
        places.append(place)
    text += "Stock: the latest stock count of " + name + " is " + str(product["current_stock"]) + " units"
    if len(places) > 0:
        text += ": " + "; ".join(places)
    text += ".\n\n"

    sold_days = item_daily[item_daily > 0]
    monthly = item_daily.groupby(item_daily.index.strftime("%B %Y")).sum()
    text += ("Online sales: " + str(int(item_daily.sum())) + " units of " + name + " were sold online between "
             + str(item_daily.index[0].date()) + " and " + str(item_daily.index[-1].date()) + ". "
             + "In the last 30 days " + str(int(item_daily.tail(30).sum())) + " units were sold, "
             + "an average of " + str(round(item_daily.tail(30).mean(), 1)) + " units per day. "
             + "The best month was " + monthly.idxmax() + " with " + str(int(monthly.max())) + " units. "
             + name + " sold on " + str(len(sold_days)) + " of " + str(len(item_daily)) + " days.\n")

    write_text(os.path.join(DOCS_FOLDER, "products"), "product_" + product["product_id"] + ".txt", text)


def write_supplier_profile(supplier, supplied_products, supplier_orders):
    name = supplier["name"]
    text = "SUPPLIER PROFILE - " + name + "\n\n"
    text += ("Supplier ID: " + str(supplier["supplier_id"]) + ". Account number: " + supplier["account_number"]
             + ". Credit rating of " + name + ": " + str(supplier["credit_rating"]) + " ("
             + CREDIT_RATINGS[supplier["credit_rating"]] + "). Preferred supplier: "
             + ("yes" if supplier["preferred"] else "no") + ". Active: "
             + ("yes" if supplier["active"] else "no") + ".\n\n")

    lines = []
    for p in supplied_products:
        lines.append(p["name"] + " (" + p["product_id"] + "): price " + money(p["price"]) + ", lead time "
                     + str(p["lead_time"]) + " days, order " + str(p["min_qty"]) + " to "
                     + str(p["max_qty"]) + " units")
    text += "Products: of the products we track, " + name + " supplies: " + "; ".join(lines) + ".\n\n"

    if len(supplier_orders) > 0:
        headers = supplier_orders.drop_duplicates("PurchaseOrderID")
        received = supplier_orders["ReceivedQty"].sum()
        rejected = supplier_orders["RejectedQty"].sum()
        rejected_percent = 0
        if received > 0:
            rejected_percent = round(rejected / received * 100, 1)
        ship_days = (headers["ShipDate"] - headers["OrderDate"]).dt.days.mean()
        text += ("Purchase history with " + name + ": " + str(len(headers)) + " purchase orders between "
                 + str(headers["OrderDate"].min().date()) + " and " + str(headers["OrderDate"].max().date())
                 + ", worth " + money(headers["TotalDue"].sum()) + " in total (with tax and freight). "
                 + str(int(received)) + " units were received and " + str(int(rejected)) + " units ("
                 + str(rejected_percent) + "%) were rejected during inspection. On average the orders "
                 + "shipped " + str(round(ship_days, 1)) + " days after they were placed.\n")

    write_text(os.path.join(DOCS_FOLDER, "suppliers"), "supplier_" + str(supplier["supplier_id"]) + ".txt", text)


def write_purchase_order(header, order_lines, supplier_name, ship_method, product_ids):
    po = str(header["PurchaseOrderID"])
    text = "PURCHASE ORDER " + po + " - " + supplier_name + "\n\n"
    text += ("Purchase order " + po + " was placed with " + supplier_name + " on "
             + str(header["OrderDate"].date()) + " and shipped on " + str(header["ShipDate"].date())
             + " by " + ship_method + ". Status: " + PO_STATUS[header["Status"]] + ".\n\n")

    text += "Items in purchase order " + po + ":\n"
    for index, line in order_lines.iterrows():
        product_name = line["ProductName"]
        if line["ProductID"] in product_ids:
            product_name += " (" + product_ids[line["ProductID"]] + ")"
        text += ("- " + product_name + ": ordered " + str(int(line["OrderQty"])) + ", received "
                 + str(int(line["ReceivedQty"])) + ", rejected " + str(int(line["RejectedQty"]))
                 + ", unit price " + money(line["UnitPrice"]) + ", line total " + money(line["LineTotal"])
                 + ", due " + str(line["DueDate"].date()) + "\n")
    text += "\n"

    text += ("Invoice amounts for purchase order " + po + ": subtotal " + money(header["SubTotal"])
             + ", tax " + money(header["TaxAmt"]) + ", freight " + money(header["Freight"])
             + ", total due " + money(header["TotalDue"]) + ".\n")

    write_text(os.path.join(DOCS_FOLDER, "purchase_orders"), "po_" + po + ".txt", text)


def contract_short_name(title):
    # "VERICELCORP_08_06_2019-EX-10.10-SUPPLY AGREEMENT"      -> "VERICELCORP"
    # "Apollo Endosurgery - Manufacturing and Supply Agreement" -> "Apollo Endosurgery"
    name = title.split(" - ")[0]
    return name.split("_")[0].strip()


def write_contracts():
    # Supply agreements from CUAD. Returns test questions made from the lawyers' labels.
    if not os.path.exists(CUAD_FILE):
        print("ERROR: could not find", CUAD_FILE)
        print("Run  python data\\download_data.py  first.")
        sys.exit(1)

    with open(CUAD_FILE, encoding="utf-8") as f:
        cuad = json.load(f)

    questions = []
    count = 0
    for contract in cuad["data"]:
        title = contract["title"]
        # only supply agreements ("affiliate" is a different kind of contract from a supply company)
        if "supply" not in title.lower() or "affiliate" in title.lower():
            continue

        name = contract_short_name(title)
        file_name = "contract_" + re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") + ".txt"
        contract_text = contract["paragraphs"][0]["context"]

        text = "SUPPLY AGREEMENT - " + name + "\n\n"
        text += ("Source of the " + name + " supply agreement: CUAD v1 by The Atticus Project (CC BY 4.0), "
                 + "original file \"" + title + "\". It is a real contract from a public SEC filing. "
                 + "It is an example supplier contract, not a contract with an Adventure Works supplier.\n\n")
        text += contract_text
        write_text(os.path.join(DOCS_FOLDER, "contracts"), file_name, text)
        count = count + 1

        # every clause the lawyers marked becomes a test question
        for qa in contract["paragraphs"][0]["qas"]:
            clause = qa["id"].split("__")[-1]
            if clause in CONTRACT_QUESTIONS and len(qa["answers"]) > 0:
                answers = []
                for a in qa["answers"]:
                    answers.append(a["text"])
                questions.append({
                    "group": "Contracts",
                    "question": CONTRACT_QUESTIONS[clause].format(name=name),
                    "expected_source": "contracts/" + file_name,
                    "expected_answer": " || ".join(answers),
                })
    print("Wrote", count, "supply contracts from CUAD")
    return questions


def write_store_summary(products_table, daily_by_product):
    first_day = daily_by_product.index.min().date()
    last_day = daily_by_product.index.max().date()

    text = "STORE SUMMARY - Adventure Works online store\n\n"
    text += ("Data source: the Microsoft AdventureWorks sample database, which is sample data for a made-up "
             + "bike company called Adventure Works Cycles. The online sales data covers " + str(first_day)
             + " to " + str(last_day) + ".\n\n")
    text += ("Products and suppliers: we track " + str(len(products_table)) + " products from "
             + str(products_table["supplier_id"].nunique()) + " main suppliers. In total "
             + str(int(daily_by_product.values.sum())) + " units of these products were sold online.\n\n")

    totals = daily_by_product.tail(365).sum().sort_values(ascending=False)
    names = products_table.set_index("product_id")["name"]
    text += "Best selling products (most units sold online in the last year):\n"
    for i in range(5):
        text += str(i + 1) + ". " + names[totals.index[i]] + " (" + str(int(totals.iloc[i])) + " units)\n"
    text += "\n"

    by_category = {}
    for index, p in products_table.iterrows():
        units = int(daily_by_product[p["product_id"]].sum())
        by_category[p["category"]] = by_category.get(p["category"], 0) + units
    ordered = sorted(by_category.items(), key=lambda pair: pair[1], reverse=True)
    text += ("Category sales: the category with the highest online sales is " + ordered[0][0] + " with "
             + str(ordered[0][1]) + " units. Units sold in each category:\n")
    for category_name, units in ordered:
        text += category_name + ": " + str(units) + " units\n"
    text += "\n"

    stock_value = (products_table["current_stock"] * products_table["unit_cost"]).sum()
    text += ("Stock: the latest stock count is " + str(int(products_table["current_stock"].sum()))
             + " units in total, worth " + money(stock_value) + " at standard cost.\n")

    write_text(DOCS_FOLDER, "store_summary.txt", text)


def main():
    print("Reading the AdventureWorks files from", AW_FOLDER)
    items = read_table("Product")
    subcategories = read_table("ProductSubcategory")
    categories = read_table("ProductCategory")
    descriptions = read_table("ProductDescription")
    description_links = read_table("ProductModelProductDescriptionCulture")
    inventory = read_table("ProductInventory")
    locations = read_table("Location")
    product_vendors = read_table("ProductVendor")
    vendors = read_table("Vendor")
    ship_methods = read_table("ShipMethod")
    po_headers = read_table("PurchaseOrderHeader")
    po_lines = read_table("PurchaseOrderDetail")
    sales_headers = read_table("SalesOrderHeader")
    sales_lines = read_table("SalesOrderDetail")
    transactions = pd.concat([read_table("TransactionHistoryArchive"), read_table("TransactionHistory")])

    for table, column in [(sales_headers, "OrderDate"), (po_headers, "OrderDate"), (po_headers, "ShipDate"),
                          (po_lines, "DueDate"), (transactions, "TransactionDate")]:
        table[column] = pd.to_datetime(table[column])

    # category and English description of every product
    subcategories = subcategories.rename(columns={"Name": "Subcategory"})
    categories = categories.rename(columns={"Name": "Category"})
    items = items.merge(subcategories[["ProductSubcategoryID", "ProductCategoryID", "Subcategory"]],
                        on="ProductSubcategoryID", how="left")
    items = items.merge(categories[["ProductCategoryID", "Category"]], on="ProductCategoryID", how="left")
    english = description_links[description_links["CultureID"].str.strip() == "en"]
    english = english.merge(descriptions[["ProductDescriptionID", "Description"]], on="ProductDescriptionID")
    items = items.merge(english[["ProductModelID", "Description"]], on="ProductModelID", how="left")
    items = items.set_index("ProductID")

    # we need to know if a supplier is preferred when a product has 2 suppliers
    product_vendors = product_vendors.merge(vendors[["BusinessEntityID", "PreferredVendorStatus"]],
                                            on="BusinessEntityID")

    # Online sales only: orders customers placed on the website (OnlineOrderFlag = 1).
    # The other orders are big monthly orders from bike shops, which stop in April 2025 in the data.
    online = sales_lines.merge(sales_headers[["SalesOrderID", "OrderDate", "OnlineOrderFlag"]],
                               on="SalesOrderID")
    online = online[online["OnlineOrderFlag"] == 1]
    daily = online.groupby(["OrderDate", "ProductID"])["OrderQty"].sum().reset_index()
    last_date = daily["OrderDate"].max()
    one_year_back = last_date - pd.Timedelta(days=365)

    # Pick products that we buy from a supplier and that were already selling online a year
    # before the data ends (so the model has enough history). Then take the best sellers of the last year.
    first_sale = daily.groupby("ProductID")["OrderDate"].min()
    candidates = first_sale[first_sale <= one_year_back].index
    candidates = [pid for pid in candidates if pid in set(product_vendors["ProductID"])]
    last_year = daily[(daily["OrderDate"] > one_year_back) & (daily["ProductID"].isin(candidates))]
    totals = last_year.groupby("ProductID")["OrderQty"].sum().sort_values(ascending=False)
    top_items = totals.head(NUMBER_OF_PRODUCTS).index.tolist()

    # all products start on the same day: the day the last of them started selling online
    start_date = first_sale[top_items].max()
    all_dates = pd.date_range(start_date, last_date, freq="D")

    clean_old_documents()

    # Units on order: purchase order lines that were not rejected and are due after the last
    # day of data, so they have not arrived yet. (Status 3 = Rejected)
    # We don't use the OnOrderQty column of ProductVendor, because in the sample data it still
    # counts orders that were already received.
    po_all_vendors = po_lines.merge(po_headers, on="PurchaseOrderID")
    open_lines = po_all_vendors[(po_all_vendors["OrderDate"] <= last_date)
                                & (po_all_vendors["DueDate"] > last_date)
                                & (po_all_vendors["Status"] != 3)]
    on_order_of = open_lines.groupby("ProductID")["OrderQty"].sum()

    # ---------- products ----------
    stock = inventory.merge(locations[["LocationID", "Name"]].rename(columns={"Name": "LocationName"}),
                            on="LocationID")
    product_rows = []
    sales_rows = []
    daily_by_product = {}
    other_suppliers_of = {}
    product_ids = {}   # AdventureWorks ProductID -> our product_id (P001...)

    number = 1
    for item_id in top_items:
        product_id = "P" + str(number).zfill(3)
        number = number + 1
        product_ids[item_id] = product_id
        item = items.loc[item_id]

        supplier, others = choose_supplier(product_vendors[product_vendors["ProductID"] == item_id])
        other_suppliers_of[product_id] = others

        description = item["Description"]
        if pd.isna(description):
            description = ""

        product_rows.append({
            "product_id": product_id,
            "aw_product_id": int(item_id),
            "name": item["Name"],
            "category": item["Subcategory"],
            "product_group": item["Category"],
            "unit_price": round(float(item["ListPrice"]), 2),     # US dollars
            "unit_cost": round(float(item["StandardCost"]), 2),
            "supplier_id": int(supplier["BusinessEntityID"]),
            "supplier_price": round(float(supplier["StandardPrice"]), 2),
            "lead_time_days": int(supplier["AverageLeadTime"]),
            "min_order_qty": int(supplier["MinOrderQty"]),
            "max_order_qty": int(supplier["MaxOrderQty"]),
            "on_order_qty": int(on_order_of.get(item_id, 0)),
            "current_stock": int(stock[stock["ProductID"] == item_id]["Quantity"].sum()),
            "description": description,
        })

        # daily units sold online, 0 on days with no sale
        item_daily = daily[daily["ProductID"] == item_id].set_index("OrderDate")["OrderQty"]
        item_daily = item_daily.reindex(all_dates, fill_value=0)
        daily_by_product[product_id] = item_daily
        for day in all_dates:
            sales_rows.append({"date": day.date(), "product_id": product_id, "quantity": int(item_daily[day])})

    products_table = pd.DataFrame(product_rows)
    daily_by_product = pd.DataFrame(daily_by_product)

    # ---------- suppliers ----------
    supplier_ids = set(products_table["supplier_id"])
    for others in other_suppliers_of.values():
        supplier_ids.update(others["BusinessEntityID"].astype(int))

    suppliers = {}
    for index, v in vendors[vendors["BusinessEntityID"].isin(supplier_ids)].iterrows():
        suppliers[int(v["BusinessEntityID"])] = {
            "supplier_id": int(v["BusinessEntityID"]),
            "name": v["Name"],
            "account_number": v["AccountNumber"],
            "credit_rating": int(v["CreditRating"]),
            "credit_rating_text": CREDIT_RATINGS[int(v["CreditRating"])],
            "preferred": int(v["PreferredVendorStatus"]),
            "active": int(v["ActiveFlag"]),
        }

    # ---------- purchase orders (only orders placed up to the last sales day) ----------
    po_all = po_lines.merge(po_headers, on="PurchaseOrderID")
    po_all = po_all[(po_all["OrderDate"] <= last_date) & (po_all["VendorID"].isin(supplier_ids))]
    po_all = po_all.merge(items[["Name"]].rename(columns={"Name": "ProductName"}),
                          left_on="ProductID", right_index=True)

    # ---------- documents ----------
    for index, product in products_table.iterrows():
        item_id = product["aw_product_id"]
        write_product_report(product, items.loc[item_id], other_suppliers_of[product["product_id"]],
                             suppliers, stock[stock["ProductID"] == item_id],
                             daily_by_product[product["product_id"]])

    for supplier_id, supplier in suppliers.items():
        supplied = []
        for index, pv in product_vendors[product_vendors["BusinessEntityID"] == supplier_id].iterrows():
            if pv["ProductID"] in product_ids:
                supplied.append({
                    "name": items.loc[pv["ProductID"], "Name"], "product_id": product_ids[pv["ProductID"]],
                    "price": pv["StandardPrice"], "lead_time": int(pv["AverageLeadTime"]),
                    "min_qty": int(pv["MinOrderQty"]), "max_qty": int(pv["MaxOrderQty"]),
                })
        write_supplier_profile(supplier, supplied, po_all[po_all["VendorID"] == supplier_id])

    # one document for every purchase order that has one of our products in it
    ship_method_names = ship_methods.set_index("ShipMethodID")["Name"]
    our_orders = po_all[po_all["ProductID"].isin(product_ids.keys())]["PurchaseOrderID"].unique()
    for po_id in our_orders:
        order_lines = po_all[po_all["PurchaseOrderID"] == po_id]
        header = order_lines.iloc[0]
        write_purchase_order(header, order_lines, suppliers[int(header["VendorID"])]["name"],
                             ship_method_names[header["ShipMethodID"]], product_ids)

    contract_questions = write_contracts()
    write_store_summary(products_table, daily_by_product)

    # ---------- stock movements from the dataset ----------
    # P = purchase order received (stock IN), S = sales order (stock OUT). Up to the last sales day.
    moves = transactions[transactions["ProductID"].isin(product_ids.keys())
                         & transactions["TransactionType"].isin(["P", "S"])
                         & (transactions["TransactionDate"] <= last_date)]
    channel = sales_headers.set_index("SalesOrderID")["OnlineOrderFlag"]
    movement_rows = []
    for index, m in moves.sort_values(["TransactionDate", "TransactionID"]).iterrows():
        if m["TransactionType"] == "P":
            move_type = "IN"
            note = "Purchase order " + str(m["ReferenceOrderID"])
        else:
            move_type = "OUT"
            if channel.get(m["ReferenceOrderID"]) == 1:
                note = "Online order SO" + str(m["ReferenceOrderID"])
            else:
                note = "Reseller order SO" + str(m["ReferenceOrderID"])
        movement_rows.append({
            "date": m["TransactionDate"].date(), "product_id": product_ids[m["ProductID"]],
            "type": move_type, "quantity": int(m["Quantity"]), "note": note,
        })

    # ---------- test questions for the document assistant ----------
    questions = []
    for index, p in products_table.iterrows():
        source = "products/product_" + p["product_id"] + ".txt"
        supplier_name = suppliers[p["supplier_id"]]["name"]
        questions.append(["Products", "What is the price of " + p["name"] + "?", source, money(p["unit_price"])])
        questions.append(["Products", "Who supplies " + p["name"] + "?", source, supplier_name])
        questions.append(["Products", "What is the lead time for " + p["name"] + "?", source,
                          str(p["lead_time_days"]) + " days"])
    for supplier_id, s in suppliers.items():
        source = "suppliers/supplier_" + str(supplier_id) + ".txt"
        questions.append(["Suppliers", "What is the credit rating of " + s["name"] + "?", source,
                          s["credit_rating_text"]])
    for po_id in our_orders[-20:]:
        total_due = po_all[po_all["PurchaseOrderID"] == po_id].iloc[0]["TotalDue"]
        questions.append(["Purchase orders", "What was the total due for purchase order " + str(po_id) + "?",
                          "purchase_orders/po_" + str(po_id) + ".txt", money(total_due)])
    questions_table = pd.DataFrame(questions, columns=["group", "question", "expected_source", "expected_answer"])
    questions_table = pd.concat([questions_table, pd.DataFrame(contract_questions)])

    # ---------- write the csv files ----------
    products_table.drop(columns=["description"]).to_csv(os.path.join(HERE, "products.csv"), index=False)
    pd.DataFrame(list(suppliers.values())).to_csv(os.path.join(HERE, "suppliers.csv"), index=False)
    pd.DataFrame(sales_rows).to_csv(os.path.join(HERE, "sales.csv"), index=False)
    pd.DataFrame(movement_rows).to_csv(os.path.join(HERE, "movements.csv"), index=False)
    questions_table.to_csv(os.path.join(HERE, "evaluation_questions.csv"), index=False)

    po_table = pd.DataFrame({
        "po_id": po_all["PurchaseOrderID"],
        "order_date": po_all["OrderDate"].dt.date,
        "ship_date": po_all["ShipDate"].dt.date,
        "due_date": po_all["DueDate"].dt.date,
        "status": po_all["Status"].map(PO_STATUS),
        "supplier_id": po_all["VendorID"],
        "product_name": po_all["ProductName"],
        "product_id": po_all["ProductID"].map(product_ids),   # empty if it is not one of our 20 products
        "order_qty": po_all["OrderQty"].astype(int),
        "unit_price": po_all["UnitPrice"].round(2),
        "received_qty": po_all["ReceivedQty"].astype(int),
        "rejected_qty": po_all["RejectedQty"].astype(int),
        "line_total": po_all["LineTotal"].round(2),
    }).sort_values(["order_date", "po_id"])
    po_table.to_csv(os.path.join(HERE, "purchase_orders.csv"), index=False)

    print("Picked these", len(products_table), "products:")
    for index, p in products_table.iterrows():
        print("  ", p["product_id"], "-", p["category"], "-", p["name"], "- supplier:",
              suppliers[p["supplier_id"]]["name"], "- stock:", p["current_stock"])
    print("Online sales from", all_dates[0].date(), "to", all_dates[-1].date())
    print("Suppliers:", len(suppliers), "| purchase order lines:", len(po_table),
          "| stock movements:", len(movement_rows))
    print("Documents:", len(products_table), "products,", len(suppliers), "suppliers,",
          len(our_orders), "purchase orders, 1 store summary")
    print("Test questions for the document assistant:", len(questions_table))


if __name__ == "__main__":
    main()
