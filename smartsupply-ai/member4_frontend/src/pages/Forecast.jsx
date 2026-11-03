// Forecast page: pick a product and see last 60 days of sales + next 30 days prediction
import { useEffect, useState } from "react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid, ResponsiveContainer,
} from "recharts";
import { api } from "../api";

export default function Forecast() {
  const [products, setProducts] = useState([]);
  const [selected, setSelected] = useState("P001");
  const [chartData, setChartData] = useState([]);
  const [metrics, setMetrics] = useState([]);
  const [error, setError] = useState("");

  // load product list and model errors once
  useEffect(() => {
    api.products()
      .then((result) => setProducts(result))
      .catch((err) => setError(err.message));
    api.metrics()
      .then((result) => setMetrics(result))
      .catch((err) => setError(err.message));
  }, []);

  // load the chart again every time a different product is selected
  useEffect(() => {
    api.forecast(selected).then((result) => {
      // put past sales and future forecast in one list for the chart
      const points = [];
      for (const h of result.history) {
        points.push({ date: h.date, Actual: h.quantity });
      }
      for (const f of result.forecast) {
        points.push({ date: f.date, Forecast: f.predicted_quantity });
      }
      setChartData(points);
    }).catch((err) => setError(err.message));
  }, [selected]);

  if (error) {
    return <p className="error">Cannot reach backend: {error}</p>;
  }

  return (
    <div>
      <h2>Demand Forecast</h2>

      <div className="panel">
        <div className="row">
          <h3 style={{ marginRight: "auto" }}>Last 60 days + next 30 days</h3>
          <select value={selected} onChange={(e) => setSelected(e.target.value)}>
            {products.map((p) => (
              <option key={p.product_id} value={p.product_id}>{p.name}</option>
            ))}
          </select>
        </div>

        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" fontSize={11} minTickGap={30} />
            <YAxis fontSize={11} />
            <Tooltip />
            <Legend />
            <Line dataKey="Actual" stroke="#2563eb" dot={false} />
            <Line dataKey="Forecast" stroke="#f97316" strokeDasharray="5 5" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="panel">
        <h3>Model Accuracy (average MAE, lower is better)</h3>
        <p className="muted">
          MAE means: on average, how many units per day the prediction is wrong by.
          We compare the ML models with a simple baseline: the average of the last 28 days.
          Each product uses the model with the lowest error, and the baseline if no model beats it.
        </p>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={metrics} layout="vertical" margin={{ left: 60 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" fontSize={11} />
            <YAxis type="category" dataKey="model" fontSize={11} width={150} />
            <Tooltip />
            <Bar dataKey="MAE" fill="#2563eb" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
