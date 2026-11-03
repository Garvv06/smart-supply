// Dashboard page: summary cards, sales charts and stock alerts
// All sales numbers come from the Kaggle dataset. Stock comes from what the user enters.
import { useEffect, useState } from "react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer,
} from "recharts";
import { api } from "../api";
import StatusBadge from "./StatusBadge";

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  // get dashboard data from the backend when the page opens
  useEffect(() => {
    api.dashboard()
      .then((result) => setData(result))
      .catch((err) => setError(err.message));
  }, []);

  if (error) {
    return <p className="error">Cannot reach backend: {error}</p>;
  }
  if (data === null) {
    return <p>Loading...</p>;
  }

  // reminder if some products still have no stock entered
  let stockNotice = null;
  if (data.stock_not_entered > 0) {
    stockNotice = (
      <div className="notice">
        {data.stock_not_entered} of {data.total_products} products have no stock entered yet.
        The dataset has only sales, so add stock on the Inventory page to get reorder alerts.
      </div>
    );
  }

  // alerts table, or a message if there are no alerts
  let alertsTable;
  if (data.alerts.length === 0) {
    alertsTable = <p className="muted">No alerts. Products with stock entered have enough stock.</p>;
  } else {
    alertsTable = (
      <table>
        <thead>
          <tr>
            <th>Product</th>
            <th>Stock</th>
            <th>Days Left</th>
            <th>Reorder Point</th>
            <th>Status</th>
            <th>Suggested Order</th>
          </tr>
        </thead>
        <tbody>
          {data.alerts.map((item) => (
            <tr key={item.product_id}>
              <td>{item.name}</td>
              <td>{item.current_stock}</td>
              <td>{item.days_of_stock_left}</td>
              <td>{item.reorder_point}</td>
              <td><StatusBadge status={item.status} /></td>
              <td>{item.suggested_order_qty}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  return (
    <div>
      <h2>Dashboard</h2>
      {stockNotice}

      <div className="cards">
        <Card title="Products" value={data.total_products} />
        <Card title="Units Sold (dataset)" value={data.total_units_sold.toLocaleString("en-IN")} />
        <Card title="Expected Demand (next 30 days)" value={data.expected_demand_30_days.toLocaleString("en-IN")} />
        <Card title="Reorder Now" value={data.reorder_now} color="red" />
        <Card title="Low Stock" value={data.low_stock} color="orange" />
      </div>

      <div className="grid-2">
        <div className="panel">
          <h3>Monthly Sales (units)</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={data.monthly_sales}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" fontSize={11} />
              <YAxis fontSize={11} />
              <Tooltip />
              <Line type="monotone" dataKey="quantity" stroke="#2563eb" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="panel">
          <h3>Units Sold by Category</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={data.sales_by_category}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="category" fontSize={11} />
              <YAxis fontSize={11} />
              <Tooltip />
              <Bar dataKey="units" fill="#2563eb" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="panel">
        <h3>Stock Alerts</h3>
        {alertsTable}
      </div>
    </div>
  );
}

// one summary box at the top of the dashboard
function Card({ title, value, color }) {
  let cardClass = "card";
  if (color) {
    cardClass = "card " + color;
  }
  return (
    <div className={cardClass}>
      <div className="card-title">{title}</div>
      <div className="card-value">{value}</div>
    </div>
  );
}
