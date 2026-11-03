# This script loads the REAL sales data from Kaggle. All data in the project comes from here.
#
# Dataset: "Predict Future Sales" (1C Company, a Russian chain selling electronics,
#          games, software and movies). Daily sales from Jan 2013 to Oct 2015.
# Link:    https://www.kaggle.com/c/competitive-data-science-predict-future-sales/data
#
# Steps:
#   1. Download the dataset (zip or the csv files) from the link above
#   2. Put it inside the data\kaggle folder
#   3. Run:  python load_kaggle_data.py
#
# What it makes:
#   products.csv  - the top selling products with their real name, category and price
#   sales.csv     - daily units sold of each product (all shops added together)
#   documents\    - a text report for each product and one store summary,
#                   written only from numbers in the dataset (used by the document assistant)
#
# The dataset has NO stock levels. Stock is entered by the user in the app (Inventory page).

import os
import sys
import zipfile
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
KAGGLE_FOLDER = os.path.join(HERE, "kaggle")
DOCS_FOLDER = os.path.join(HERE, "documents")
NUMBER_OF_PRODUCTS = 20

# The category names in the dataset are in Russian.
# We translate only the main part of the name to English.
# (Order matters: "Игры PC" must be checked before "Игры")
CATEGORY_NAMES = [
    ["Игровые консоли", "Game Consoles"],
    ["Игры PC", "PC Games"],
    ["Игры MAC", "Mac Games"],
    ["Игры Android", "Android Games"],
    ["Игры", "Console Games"],
    ["Аксессуары", "Accessories"],
    ["Кино", "Movies"],
    ["Музыка", "Music"],
    ["Книги", "Books"],
    ["Подарки", "Gifts"],
    ["Программы", "Software"],
    ["Карты оплаты", "Payment Cards"],
    ["Чистые носители", "Blank Media"],
    ["Элементы питания", "Batteries"],
    ["PC", "PC Accessories"],
    ["Доставка", "Delivery"],
    ["Служебные", "Service"],
    ["Билеты", "Tickets"],
]

# These rows are not products you keep in stock, so we leave them out
SKIP_CATEGORIES = ["Delivery", "Service", "Tickets"]
SKIP_ITEMS = [20949]   # a plastic carry bag given at the counter


def translate_category(russian_name):
    for pair in CATEGORY_NAMES:
        if russian_name.startswith(pair[0]):
            return pair[1]
    return "Other"


def unzip_downloads():
    # Kaggle gives a .zip file. If it is still zipped, we unzip it here.
    for root, folders, files in os.walk(KAGGLE_FOLDER):
        for file_name in files:
            if file_name.endswith(".zip"):
                print("Unzipping", file_name)
                with zipfile.ZipFile(os.path.join(root, file_name)) as z:
                    z.extractall(root)


def find_file(name):
    # Look for the file anywhere inside the kaggle folder (also in sub-folders).
    # Some downloads have sales_train.csv.gz, pandas can read that too.
    for root, folders, files in os.walk(KAGGLE_FOLDER):
        if name in files:
            return os.path.join(root, name)
        if name + ".gz" in files:
            return os.path.join(root, name + ".gz")

    print()
    print("ERROR: could not find", name, "inside", KAGGLE_FOLDER)
    print("Put sales_train.csv, items.csv and item_categories.csv in the data\\kaggle folder.")
    sys.exit(1)


def write_product_report(product, item_sales_rows, daily_sales):
    # One text file per product. Every number here is calculated from the dataset.
    name = product["name"]
    prices = item_sales_rows["item_price"]

    total_units = int(item_sales_rows["item_cnt_day"].sum())
    first_day = item_sales_rows["date"].min().date()
    last_day = item_sales_rows["date"].max().date()
    last_30 = int(daily_sales.tail(30).sum())

    monthly = item_sales_rows.groupby(item_sales_rows["date"].dt.strftime("%B %Y"))["item_cnt_day"].sum()
    best_month = monthly.idxmax()
    best_month_units = int(monthly.max())

    by_shop = item_sales_rows.groupby("shop_id")["item_cnt_day"].sum()
    number_of_shops = len(by_shop)
    best_shop = by_shop.idxmax()
    best_shop_units = int(by_shop.max())

    text = "PRODUCT REPORT - " + name + "\n\n"
    text += ("Product ID: " + product["product_id"] + ". Item number in the dataset: "
             + str(product["item_id"]) + ". Category: " + product["category"]
             + " (" + product["original_category"] + ").\n\n")
    text += ("Price: the usual selling price of " + name + " is " + str(round(prices.median()))
             + " roubles. The lowest price was " + str(round(prices.min()))
             + " roubles and the highest price was " + str(round(prices.max())) + " roubles.\n\n")
    text += ("Total sales: " + str(total_units) + " units of " + name + " were sold between "
             + str(first_day) + " and " + str(last_day) + ". In the last 30 days "
             + str(last_30) + " units were sold.\n\n")
    text += ("Best month: the most units of " + name + " were sold in " + best_month
             + " (" + str(best_month_units) + " units).\n\n")
    text += ("Shops: " + name + " was sold in " + str(number_of_shops)
             + " shops. Shop number " + str(best_shop) + " sold the most, "
             + str(best_shop_units) + " units.\n")

    file_name = "product_" + product["product_id"] + ".txt"
    with open(os.path.join(DOCS_FOLDER, file_name), "w", encoding="utf-8") as f:
        f.write(text)


def write_store_summary(sales, items, product_rows):
    # One summary file about the whole dataset. Every number comes from the dataset.
    first_day = sales["date"].min().date()
    last_day = sales["date"].max().date()
    number_of_shops = sales["shop_id"].nunique()
    number_of_items = sales["item_id"].nunique()
    total_units = int(sales["item_cnt_day"].sum())

    text = "STORE SUMMARY - 1C Company sales data\n\n"
    text += ("Data period: the sales data covers " + str(first_day) + " to " + str(last_day)
             + ". It has sales from " + str(number_of_shops) + " shops and "
             + str(number_of_items) + " different items.\n\n")
    text += "Total units sold: " + str(total_units) + " units were sold in this period in all shops.\n\n"

    text += "Best selling products (most units sold in the last year):\n"
    for i in range(min(5, len(product_rows))):
        text += str(i + 1) + ". " + product_rows[i]["name"] + "\n"
    text += "\n"

    # units sold in each category
    sales_with_category = sales.merge(items[["item_id", "category"]], on="item_id")
    by_category = sales_with_category.groupby("category")["item_cnt_day"].sum()
    by_category = by_category.sort_values(ascending=False)

    text += ("Category sales: the category with the highest sales is " + by_category.index[0]
             + " with " + str(int(by_category.iloc[0])) + " units sold. Units sold in each category:\n")
    for category_name in by_category.index:
        text += category_name + ": " + str(int(by_category[category_name])) + " units\n"

    with open(os.path.join(DOCS_FOLDER, "store_summary.txt"), "w", encoding="utf-8") as f:
        f.write(text)


def main():
    if not os.path.isdir(KAGGLE_FOLDER):
        print("ERROR: the folder", KAGGLE_FOLDER, "does not exist.")
        print("Make a folder called kaggle inside the data folder and put the Kaggle files in it.")
        sys.exit(1)

    unzip_downloads()
    sales_file = find_file("sales_train.csv")
    items_file = find_file("items.csv")
    categories_file = find_file("item_categories.csv")

    print("Reading", sales_file)
    sales = pd.read_csv(sales_file)
    items = pd.read_csv(items_file)
    categories = pd.read_csv(categories_file)
    print("Read", len(sales), "sales rows and", len(items), "items")

    # dates are written like 02.01.2013 (day.month.year)
    sales["date"] = pd.to_datetime(sales["date"], format="%d.%m.%Y")

    # add the category name to every item
    items = items.merge(categories, on="item_category_id")
    items["category"] = items["item_category_name"].apply(translate_category)

    # leave out rows that are not stock items
    items = items[~items["category"].isin(SKIP_CATEGORIES)]
    items = items[~items["item_id"].isin(SKIP_ITEMS)]
    sales = sales[sales["item_id"].isin(items["item_id"])]

    # Around 60 shops are in the data. We add all shops together like one big store.
    daily = sales.groupby(["date", "item_id"])["item_cnt_day"].sum().reset_index()

    # Only items that were already selling 1 year before the data ends,
    # so the model has enough history to learn from.
    last_date = daily["date"].max()
    one_year_back = last_date - pd.Timedelta(days=365)
    first_sale = daily.groupby("item_id")["date"].min()
    old_items = first_sale[first_sale <= one_year_back].index

    # From those, take the items that sold the most units in the last year
    last_year = daily[daily["date"] > one_year_back]
    last_year = last_year[last_year["item_id"].isin(old_items)]
    totals = last_year.groupby("item_id")["item_cnt_day"].sum()
    totals = totals.sort_values(ascending=False)
    top_items = totals.head(NUMBER_OF_PRODUCTS).index.tolist()

    # remove old reports made by this script (files uploaded by users are kept)
    os.makedirs(DOCS_FOLDER, exist_ok=True)
    for file_name in os.listdir(DOCS_FOLDER):
        if file_name.startswith("product_P") or file_name == "store_summary.txt":
            os.remove(os.path.join(DOCS_FOLDER, file_name))

    all_dates = pd.date_range(daily["date"].min(), last_date, freq="D")
    product_rows = []
    sales_rows = []

    number = 1
    for item_id in top_items:
        product_id = "P" + str(number).zfill(3)
        number = number + 1

        item = items[items["item_id"] == item_id].iloc[0]
        item_sales_rows = sales[sales["item_id"] == item_id]

        # daily units sold, 0 on days with no sale
        item_daily = daily[daily["item_id"] == item_id].set_index("date")["item_cnt_day"]
        item_daily = item_daily.reindex(all_dates, fill_value=0)
        item_daily = item_daily.clip(lower=0)   # negative numbers in the data are returns

        for day in all_dates:
            sales_rows.append({
                "date": day.date(),
                "product_id": product_id,
                "quantity": int(item_daily[day]),
            })

        product = {
            "product_id": product_id,
            "item_id": int(item_id),
            "name": item["item_name"],                  # real name from the dataset
            "category": item["category"],
            "original_category": item["item_category_name"],
            "unit_price": round(item_sales_rows["item_price"].median()),   # in roubles
        }
        product_rows.append(product)
        write_product_report(product, item_sales_rows, item_daily)

    write_store_summary(sales, items, product_rows)

    products_table = pd.DataFrame(product_rows)
    products_table = products_table[["product_id", "item_id", "name", "category", "unit_price"]]
    products_table.to_csv(os.path.join(HERE, "products.csv"), index=False, encoding="utf-8")
    pd.DataFrame(sales_rows).to_csv(os.path.join(HERE, "sales.csv"), index=False)

    print("Picked these", len(product_rows), "products:")
    for p in product_rows:
        print("  ", p["product_id"], "-", p["category"], "-", p["name"])
    print("Sales from", all_dates[0].date(), "to", all_dates[-1].date())
    print("Wrote", len(product_rows) + 1, "report files in the documents folder")


if __name__ == "__main__":
    main()
