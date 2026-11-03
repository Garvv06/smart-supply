# Member 1 - Demand Forecasting and Reorder Suggestions
#
# Steps:
#   1. Read the daily sales of every product
#   2. Make simple features from the date (trend, day of week, month)
#   3. Train Linear Regression and Random Forest
#   4. Compare them with a simple baseline (average of last 30 days)
#   5. Use the better model to predict the next 30 days
#   6. Use the prediction and current stock to decide if we should reorder
#
# All sales data comes from the Kaggle dataset (run data/load_kaggle_data.py first).
#
# Output files (in the "output" folder):
#   forecast.csv            - predicted sales for the next 30 days
#   model_metrics.csv       - error (MAE) of each model
#   reorder_suggestions.csv - stock status and how much to order
#
# Run:  python forecast.py

import os
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(HERE, "..", "data")
OUTPUT_FOLDER = os.path.join(HERE, "output")
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

TEST_DAYS = 60       # we keep the last 60 days to test the models
FORECAST_DAYS = 30   # we predict 30 days ahead

# Store settings. These are NOT in the dataset, the store decides them. Change if needed.
SAFETY_DAYS = 7      # keep 7 days of extra stock in case sales go up
LEAD_TIME_DAYS = 7   # days the supplier takes to deliver after we order


def make_features(dates, start_date):
    # A model cannot understand a date directly, so we turn it into numbers:
    #   day_number  - how many days since the start (to catch growth over time)
    #   day_of_week - 0 = Monday ... 6 = Sunday (weekends sell differently)
    #   month       - 1 to 12 (some months sell more, like festival season)
    df = pd.DataFrame({"date": dates})
    df["day_number"] = (df["date"] - start_date).dt.days
    df["day_of_week"] = df["date"].dt.dayofweek
    df["month"] = df["date"].dt.month

    # One-hot encoding: makes a separate yes/no column for each day and month.
    # Without this, Linear Regression would think month 12 is "bigger" than month 1.
    df = pd.get_dummies(df, columns=["day_of_week", "month"])
    df = df.drop(columns=["date"])
    return df


def forecast_product(product_sales):
    # Train, test and forecast for one product
    product_sales = product_sales.sort_values("date")
    start_date = product_sales["date"].min()

    X = make_features(product_sales["date"], start_date)
    y = product_sales["quantity"].values

    # Old data is for training, the last 60 days are for testing.
    # (For time series we always test on the latest days, not random days.)
    X_train = X[:-TEST_DAYS]
    X_test = X[-TEST_DAYS:]
    y_train = y[:-TEST_DAYS]
    y_test = y[-TEST_DAYS:]

    errors = {}

    # Baseline: just guess the average of the last 30 days for every day
    last_30_avg = y_train[-30:].mean()
    baseline_guess = [last_30_avg] * TEST_DAYS
    errors["Baseline (30-day avg)"] = mean_absolute_error(y_test, baseline_guess)

    # Model 1: Linear Regression
    lr = LinearRegression()
    lr.fit(X_train, y_train)
    errors["Linear Regression"] = mean_absolute_error(y_test, lr.predict(X_test))

    # Model 2: Random Forest
    rf = RandomForestRegressor(n_estimators=100, random_state=42)
    rf.fit(X_train, y_train)
    errors["Random Forest"] = mean_absolute_error(y_test, rf.predict(X_test))

    # Pick the model with the lower error
    if errors["Random Forest"] < errors["Linear Regression"]:
        best_name = "Random Forest"
        best_model = rf
    else:
        best_name = "Linear Regression"
        best_model = lr

    # Train the best model again on all the data, then predict the next 30 days
    best_model.fit(X, y)
    first_future_day = product_sales["date"].max() + pd.Timedelta(days=1)
    future_dates = pd.date_range(first_future_day, periods=FORECAST_DAYS)

    X_future = make_features(future_dates, start_date)
    # make sure the future table has the same columns as the training table
    X_future = X_future.reindex(columns=X.columns, fill_value=0)

    predictions = best_model.predict(X_future)
    predictions = predictions.clip(min=0).round()   # no negative sales

    forecast = pd.DataFrame({
        "date": future_dates.date,
        "predicted_quantity": predictions.astype(int),
    })
    return forecast, errors, best_name


def reorder_suggestion(product, forecast):
    # Rules:
    #   safety stock  = 7 days of average predicted sales
    #   reorder point = (average daily sales x lead time) + safety stock
    avg_daily = forecast["predicted_quantity"].mean()
    safety_stock = avg_daily * SAFETY_DAYS
    reorder_point = avg_daily * LEAD_TIME_DAYS + safety_stock
    demand_30_days = forecast["predicted_quantity"].sum()

    # The dataset has no stock. Stock is only known after the user enters it in the app.
    stock = None
    if "current_stock" in product and not pd.isna(product["current_stock"]):
        stock = int(product["current_stock"])

    if stock is None:
        status = "Stock not entered"
    elif stock <= reorder_point:
        status = "Reorder Now"
    elif stock <= reorder_point * 1.5:
        status = "Low"
    else:
        status = "OK"

    # How much to order: enough for the next 30 days plus safety stock
    order_qty = 0
    if stock is None:
        # stock is unknown, so we show how much is needed for the next 30 days
        order_qty = int(round(demand_30_days + safety_stock, -1))
    elif status != "OK":
        need = demand_30_days + safety_stock - stock
        if need > 0:
            order_qty = int(round(need, -1))   # round to nearest 10

    # How many days the current stock will last
    days_left = None
    if stock is not None and avg_daily > 0:
        days_left = round(stock / avg_daily, 1)

    return {
        "product_id": product["product_id"],
        "name": product["name"],
        "current_stock": stock,
        "avg_daily_demand": round(float(avg_daily), 1),
        "days_of_stock_left": days_left,
        "reorder_point": int(reorder_point),
        "status": status,
        "suggested_order_qty": order_qty,
    }


def main():
    products = pd.read_csv(os.path.join(DATA_FOLDER, "products.csv"))
    sales = pd.read_csv(os.path.join(DATA_FOLDER, "sales.csv"), parse_dates=["date"])

    all_forecasts = []
    all_errors = []
    all_reorders = []

    for index, product in products.iterrows():
        product_id = product["product_id"]
        product_sales = sales[sales["product_id"] == product_id]

        forecast, errors, best_name = forecast_product(product_sales)

        forecast.insert(0, "product_id", product_id)
        all_forecasts.append(forecast)

        for model_name in errors:
            all_errors.append({
                "product_id": product_id,
                "model": model_name,
                "MAE": round(errors[model_name], 2),
                "chosen": model_name == best_name,
            })

        all_reorders.append(reorder_suggestion(product, forecast))
        print(product_id, product["name"], "-> best model:", best_name)

    pd.concat(all_forecasts).to_csv(os.path.join(OUTPUT_FOLDER, "forecast.csv"), index=False)
    pd.DataFrame(all_errors).to_csv(os.path.join(OUTPUT_FOLDER, "model_metrics.csv"), index=False)
    pd.DataFrame(all_reorders).to_csv(os.path.join(OUTPUT_FOLDER, "reorder_suggestions.csv"), index=False)

    # Average error of each model over all products
    summary = pd.DataFrame(all_errors).groupby("model")["MAE"].mean().round(2)
    print()
    print("Average MAE of each model (lower is better):")
    print(summary.to_string())


if __name__ == "__main__":
    main()
