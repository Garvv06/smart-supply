# Downloads the two public datasets used by the project. No account or login is needed.
#
# 1. Microsoft AdventureWorks sample database (MIT licence)
#    Official sample data from Microsoft for a bike company "Adventure Works Cycles".
#    It has products, suppliers, stock counts, purchase orders, sales orders and stock movements.
#    https://github.com/microsoft/sql-server-samples/tree/master/samples/databases/adventure-works
#
# 2. CUAD - Contract Understanding Atticus Dataset (CC BY 4.0)
#    510 real commercial contracts from public SEC filings, labelled by lawyers.
#    We use the supply agreements as supplier contracts for the document assistant.
#    https://huggingface.co/datasets/theatticusproject/cuad
#
# Files that are already downloaded are skipped.
#
# Run:  python download_data.py

import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ADVENTUREWORKS_FOLDER = os.path.join(HERE, "adventureworks")
CUAD_FOLDER = os.path.join(HERE, "cuad")

ADVENTUREWORKS_URL = ("https://raw.githubusercontent.com/microsoft/sql-server-samples/master/"
                      "samples/databases/adventure-works/oltp-install-script/")
ADVENTUREWORKS_FILES = [
    "Product.csv", "ProductCategory.csv", "ProductSubcategory.csv",
    "ProductDescription.csv", "ProductModelProductDescriptionCulture.csv",
    "ProductInventory.csv", "Location.csv",
    "ProductVendor.csv", "Vendor.csv", "ShipMethod.csv",
    "PurchaseOrderHeader.csv", "PurchaseOrderDetail.csv",
    "SalesOrderHeader.csv", "SalesOrderDetail.csv",
    "TransactionHistory.csv", "TransactionHistoryArchive.csv",
]

CUAD_URL = "https://huggingface.co/datasets/theatticusproject/cuad/resolve/main/CUAD_v1/CUAD_v1.json"


def download(url, save_path):
    if os.path.exists(save_path):
        print("Already downloaded:", os.path.basename(save_path))
        return
    print("Downloading", os.path.basename(save_path), "...")
    urllib.request.urlretrieve(url, save_path + ".part")
    os.replace(save_path + ".part", save_path)   # only keep the file if the download finished


def main():
    os.makedirs(ADVENTUREWORKS_FOLDER, exist_ok=True)
    os.makedirs(CUAD_FOLDER, exist_ok=True)

    for file_name in ADVENTUREWORKS_FILES:
        download(ADVENTUREWORKS_URL + file_name, os.path.join(ADVENTUREWORKS_FOLDER, file_name))

    download(CUAD_URL, os.path.join(CUAD_FOLDER, "CUAD_v1.json"))
    print("All data files are ready.")


if __name__ == "__main__":
    main()
