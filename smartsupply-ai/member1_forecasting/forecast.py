# Member 1 - Demand Forecasting and Reorder Suggestions
#
# Steps:
#   1. Read the daily online sales of every product
#   2. Make features: day of week, trend, and the average sales of the last 7 and 28 days
#   3. Test 3 ML models and a simple baseline on the last 3 months (one month at a time)
#   4. Use the model with the lowest error to predict the next 30 days
#   5. Safety stock comes from how wrong the forecast was in testing and the supplier's lead time
#   6. Compare the reorder point with the stock position (stock on hand + stock on order)
#
# All data comes from the AdventureWorks dataset (run data/load_data.py first).
#
# Output files (in the "output" folder):
#   forecast.csv            - predicted sales for the next 30 days
#   model_metrics.csv       - error (MAE) of each model for each product
#   forecast_settings.csv   - chosen model and forecast error of each product
#   reorder_suggestions.csv - stock status and how much to order
# It also writes the inventory policy document for the document assistant:
#   data/documents/policies/inventory_policy.txt
#
# Run:  python forecast.py

import os
import math
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(HERE, "..", "data")
OUTPUT_FOLDER = os.path.join(HERE, "output")
POLICY_FOLDER = os.path.join(DATA_FOLDER, "documents", "policies")

FORECAST_DAYS = 30   # we predict 30 days ahead
TEST_MONTHS = 3      # we test on the last 3 blocks of 30 days
HISTORY_DAYS = 28    # the features look back 28 days (4 full weeks)

# Inventory policy settings (the store decides these, they are not in the dataset)
SERVICE_LEVEL = "95%"
SAFETY_FACTOR = 1.65  # z value for a 95% service level
REVIEW_DAYS = 30      # an order should last the lead time + 30 more days
LOW_STOCK_DAYS = 7    # "Low" = the reorder point will be reached within 7 days

BASELINE = "Baseline (28-day average)"


def make_models():
    # a new, untrained copy of every model
    return {
        "Linear Regression": LinearRegression(),
        "Random Forest": RandomForestRegressor(n_estimators=100, min_samples_leaf=5, random_state=42),
        "Gradient Boosting": GradientBoostingRegressor(n_estimators=100, max_depth=2, random_state=42),
    }


def make_features(day, past, start_date):
    # A model cannot understand a date directly, so we turn it into numbers.
    # "past" is the list of daily sales before this day.
    #   day_number   - days since the start (to catch growth or decline over time)
    #   last_7_avg   - average sales of the last 7 days (recent level)
    #   last_28_avg  - average sales of the last 28 days (longer level)
    #   same_day_last_week - sales on the same weekday one week ago
    #   dow_0..dow_6 - one yes/no column for each day of the week (0 = Monday).
    #                  One-hot, so Linear Regression does not think Sunday (6) is "bigger" than Monday (0).
    row = {
        "day_number": (day - start_date).days,
        "last_7_avg": sum(past[-7:]) / 7,
        "last_28_avg": sum(past[-HISTORY_DAYS:]) / HISTORY_DAYS,
        "same_day_last_week": past[-7],
    }
    for weekday in range(7):
        row["dow_" + str(weekday)] = 1 if day.day_of_week == weekday else 0
    return row


def training_table(dates, values, start_date):
    # one row per day; the first 28 days are only used as history
    rows = []
    targets = []
    for i in range(HISTORY_DAYS, len(values)):
        rows.append(make_features(dates[i], values[:i], start_date))
        targets.append(values[i])
    return pd.DataFrame(rows), targets


def predict_days(model, past_values, future_dates, start_date):
    # We predict one day at a time. Each prediction is added to the history,
    # so the next day's "last 7 days average" can use it (we don't know the real sales yet).
    past = list(past_values)
    predictions = []
    for day in future_dates:
        X = pd.DataFrame([make_features(day, past, start_date)])
        prediction = max(0.0, float(model.predict(X)[0]))   # no negative sales
        predictions.append(prediction)
        past.append(prediction)
    return predictions


def forecast_product(product_sales):
    # Test, choose and forecast for one product
    product_sales = product_sales.sort_values("date")
    dates = list(product_sales["date"])
    values = [float(v) for v in product_sales["quantity"]]
    start_date = dates[0]

    # Testing: we pretend it is 90, 60 and 30 days before the end of the data,
    # train on the days before that, and predict the next 30 days.
    # (For time series we always test on later days than we train on, never random days.)
    names = [BASELINE] + list(make_models().keys())
    errors = {}      # name -> list of (actual - predicted) for every test day
    for name in names:
        errors[name] = []
    actual_total = 0
    month_total_errors = {}   # name -> how wrong the 30-day total was, added up over the 3 months
    for name in names:
        month_total_errors[name] = 0

    for month in range(TEST_MONTHS, 0, -1):
        cut = len(values) - month * FORECAST_DAYS
        train_values = values[:cut]
        test_values = values[cut:cut + FORECAST_DAYS]
        test_dates = dates[cut:cut + FORECAST_DAYS]
        actual_total += sum(test_values)

        # Baseline: the average of the last 28 days, for every day
        guess = sum(train_values[-HISTORY_DAYS:]) / HISTORY_DAYS
        for actual in test_values:
            errors[BASELINE].append(actual - guess)
        month_total_errors[BASELINE] += abs(sum(test_values) - guess * len(test_values))

        X_train, y_train = training_table(dates[:cut], train_values, start_date)
        for name, model in make_models().items():
            model.fit(X_train, y_train)
            predictions = predict_days(model, train_values, test_dates, start_date)
            for actual, predicted in zip(test_values, predictions):
                errors[name].append(actual - predicted)
            month_total_errors[name] += abs(sum(test_values) - sum(predictions))

    # MAE = average of how many units per day we were wrong by
    results = {}
    for name in names:
        absolute = [abs(e) for e in errors[name]]
        mean_error = sum(errors[name]) / len(errors[name])
        variance = sum((e - mean_error) ** 2 for e in errors[name]) / (len(errors[name]) - 1)
        results[name] = {
            "MAE": sum(absolute) / len(absolute),
            "MAE_percent": sum(absolute) / actual_total * 100,   # error compared to the real sales
            # For ordering the 30-day total matters most, because daily ups and downs cancel out
            "month_error_percent": month_total_errors[name] / actual_total * 100,
            "error_std": math.sqrt(variance),                    # used for safety stock
        }

    # Pick the lowest error. If no ML model beats the baseline, we use the baseline.
    best_name = min(names, key=lambda n: results[n]["MAE"])

    # Train the best model again on all the data, then predict the next 30 days
    future_dates = pd.date_range(dates[-1] + pd.Timedelta(days=1), periods=FORECAST_DAYS)
    if best_name == BASELINE:
        predictions = [sum(values[-HISTORY_DAYS:]) / HISTORY_DAYS] * FORECAST_DAYS
    else:
        model = make_models()[best_name]
        X_all, y_all = training_table(dates, values, start_date)
        model.fit(X_all, y_all)
        predictions = predict_days(model, values, future_dates, start_date)

    forecast = pd.DataFrame({
        "date": future_dates.date,
        "predicted_quantity": [round(p, 1) for p in predictions],
    })
    return forecast, results, best_name


def reorder_suggestion(product, forecast):
    # Rules (the same rules are written in the inventory policy document):
    #   safety stock   = 1.65 x forecast error x square root of the lead time
    #   reorder point  = average daily forecast x lead time + safety stock
    #   stock position = stock on hand + stock already on order
    avg_daily = float(forecast["predicted_quantity"].mean())
    lead_time = int(product["lead_time_days"])

    error_std = product.get("forecast_error_std")
    if error_std is None or pd.isna(error_std):
        error_std = avg_daily   # no test result yet, so we are careful and keep more stock

    safety_stock = SAFETY_FACTOR * error_std * math.sqrt(lead_time)
    reorder_point = avg_daily * lead_time + safety_stock

    stock = product.get("current_stock")
    if stock is None or pd.isna(stock):
        stock = 0
    stock = int(stock)
    on_order = product.get("on_order_qty")
    if on_order is None or pd.isna(on_order):
        on_order = 0
    on_order = int(on_order)
    position = stock + on_order

    if position <= reorder_point:
        status = "Reorder Now"
    elif position - avg_daily * LOW_STOCK_DAYS <= reorder_point:
        status = "Low"
    else:
        status = "OK"

    # How much to order: enough for the lead time + 30 days, plus safety stock,
    # minus what we have and what is already coming. The supplier's min and max order apply.
    order_qty = 0
    if status != "OK":
        need = avg_daily * (lead_time + REVIEW_DAYS) + safety_stock - position
        if need > 0:
            order_qty = math.ceil(need)
            order_qty = max(order_qty, int(product["min_order_qty"]))
            order_qty = min(order_qty, int(product["max_order_qty"]))

    # How many days the stock on hand will last
    days_left = None
    if avg_daily > 0:
        days_left = round(stock / avg_daily, 1)

    return {
        "product_id": product["product_id"],
        "name": product["name"],
        "current_stock": stock,
        "on_order_qty": on_order,
        "avg_daily_demand": round(avg_daily, 1),
        "days_of_stock_left": days_left,
        "lead_time_days": lead_time,
        "safety_stock": math.ceil(safety_stock),
        "reorder_point": math.ceil(reorder_point),
        "status": status,
        "suggested_order_qty": order_qty,
        "order_value": round(order_qty * float(product["supplier_price"]), 2),
    }


def write_policy_document(settings_rows, reorder_rows):
    # The inventory policy for the document assistant. The rules are the same as in reorder_suggestion.
    text = "INVENTORY POLICY - SmartSupply AI\n\n"
    text += ("About this inventory policy: it was written by the SmartSupply team. The rules below are the rules "
             + "the app uses for every product. The numbers for each product are calculated from the dataset "
             + "by forecast.py.\n\n")
    text += ("Service level: the inventory policy aims for a " + SERVICE_LEVEL + " service level, which means "
             + "having enough stock in 95 out of 100 order cycles. This gives a safety factor (z) of "
             + str(SAFETY_FACTOR) + ".\n\n")
    text += ("Safety stock: safety stock = " + str(SAFETY_FACTOR) + " x forecast error x square root of the "
             + "supplier lead time in days. The forecast error is the standard deviation of the daily forecast "
             + "errors found when the forecast was tested on the last 3 months.\n\n")
    text += ("Lead time: the lead time is the supplier's average number of days between placing an order "
             + "and receiving the products. It comes from the supplier data.\n\n")
    text += ("Reorder point: reorder point = average daily forecast x lead time + safety stock.\n\n")
    text += ("When to reorder: compare the reorder point with the stock position. The stock position is the "
             + "stock on hand plus the units already on order. If the stock position is at or below the reorder "
             + "point, the status is Reorder Now. If it will reach the reorder point within " + str(LOW_STOCK_DAYS)
             + " days, the status is Low. Otherwise the status is OK.\n\n")
    text += ("How much to order: an order should cover the lead time plus " + str(REVIEW_DAYS) + " more days of "
             + "forecast demand, plus the safety stock, minus the stock position. The quantity must be between "
             + "the supplier's minimum and maximum order quantity.\n\n")
    text += ("Who places the order: the app only suggests orders. A person checks the suggestion and places "
             + "the purchase order with the supplier. Rejected units found during inspection are not added to stock.\n\n")

    text += "Reorder settings per product:\n"
    for settings, reorder in zip(settings_rows, reorder_rows):
        text += (reorder["name"] + " (" + reorder["product_id"] + "): lead time " + str(reorder["lead_time_days"])
                 + " days, safety stock " + str(reorder["safety_stock"]) + " units, reorder point "
                 + str(reorder["reorder_point"]) + " units, forecast model " + settings["best_model"] + "\n")

    os.makedirs(POLICY_FOLDER, exist_ok=True)
    with open(os.path.join(POLICY_FOLDER, "inventory_policy.txt"), "w", encoding="utf-8") as f:
        f.write(text)


def main():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    products = pd.read_csv(os.path.join(DATA_FOLDER, "products.csv"))
    sales = pd.read_csv(os.path.join(DATA_FOLDER, "sales.csv"), parse_dates=["date"])

    all_forecasts = []
    all_metrics = []
    all_settings = []
    all_reorders = []

    for index, product in products.iterrows():
        product_id = product["product_id"]
        product_sales = sales[sales["product_id"] == product_id]

        forecast, results, best_name = forecast_product(product_sales)

        forecast.insert(0, "product_id", product_id)
        all_forecasts.append(forecast)

        for model_name in results:
            all_metrics.append({
                "product_id": product_id,
                "model": model_name,
                "MAE": round(results[model_name]["MAE"], 2),
                "MAE_percent": round(results[model_name]["MAE_percent"], 1),
                "month_error_percent": round(results[model_name]["month_error_percent"], 1),
                "chosen": model_name == best_name,
            })

        settings = {
            "product_id": product_id,
            "best_model": best_name,
            "forecast_mae": round(results[best_name]["MAE"], 2),
            "forecast_error_std": round(results[best_name]["error_std"], 3),
        }
        all_settings.append(settings)

        product = product.copy()
        product["forecast_error_std"] = settings["forecast_error_std"]
        all_reorders.append(reorder_suggestion(product, forecast))
        print(product_id, product["name"], "-> best model:", best_name,
              "| MAE", settings["forecast_mae"], "units/day")

    pd.concat(all_forecasts).to_csv(os.path.join(OUTPUT_FOLDER, "forecast.csv"), index=False)
    pd.DataFrame(all_metrics).to_csv(os.path.join(OUTPUT_FOLDER, "model_metrics.csv"), index=False)
    pd.DataFrame(all_settings).to_csv(os.path.join(OUTPUT_FOLDER, "forecast_settings.csv"), index=False)
    pd.DataFrame(all_reorders).to_csv(os.path.join(OUTPUT_FOLDER, "reorder_suggestions.csv"), index=False)
    write_policy_document(all_settings, all_reorders)

    # Average error of each model over all products, and how often each model was the best
    metrics = pd.DataFrame(all_metrics)
    summary = metrics.groupby("model").agg(MAE=("MAE", "mean"), MAE_percent=("MAE_percent", "mean"),
                                           month_error_percent=("month_error_percent", "mean"),
                                           times_chosen=("chosen", "sum")).round(2)
    print()
    print("Average error of each model on the last 3 months (lower is better):")
    print(summary.sort_values("MAE").to_string())
    print()
    statuses = pd.DataFrame(all_reorders)["status"].value_counts()
    print("Stock status:", statuses.to_dict())


if __name__ == "__main__":
    main()
