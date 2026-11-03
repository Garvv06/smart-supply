// Inventory page: product list with category and supplier filters, and a form to add stock IN or OUT
// The starting stock comes from the latest stock count in the dataset; the user adds movements here.
import { useEffect, useState } from "react";
import { api } from "../api";
import StatusBadge from "./StatusBadge";

// gives a list without repeated values, e.g. every category once
function uniqueValues(list, key) {
  const values = [];
  for (const item of list) {
    if (!values.includes(item[key])) {
      values.push(item[key]);
    }
  }
  return values;
}

// show a dash when a value is empty (like stock that is not entered yet)
function showValue(value) {
  if (value === null || value === undefined) {
    return "-";
  }
  return value;
}

export default function Inventory() {
  const [items, setItems] = useState([]);
  const [movements, setMovements] = useState([]);
  const [category, setCategory] = useState("");
  const [supplier, setSupplier] = useState("");
  const [loadError, setLoadError] = useState("");

  // form fields
  const [productId, setProductId] = useState("P001");
  const [type, setType] = useState("IN");
  const [quantity, setQuantity] = useState("");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");

  function loadData() {
    api.reorder()
      .then((result) => setItems(result))
      .catch((err) => setLoadError(err.message));
    api.movements()
      .then((result) => setMovements(result))
      .catch((err) => setLoadError(err.message));
  }

  useEffect(() => {
    loadData();
  }, []);

  async function saveMovement(e) {
    e.preventDefault();   // stop the page from reloading
    try {
      await api.addMovement({
        product_id: productId,
        type: type,
        quantity: Number(quantity),
        note: note,
      });
      setMessage("Stock updated");
      setQuantity("");
      setNote("");
      loadData();
    } catch (err) {
      setMessage("Error: " + err.message);
    }
  }

  if (loadError) {
    return <p className="error">Cannot reach backend: {loadError}</p>;
  }

  const categories = uniqueValues(items, "category");
  const suppliers = uniqueValues(items, "supplier_name");

  // only show products of the selected category and supplier
  const shownItems = [];
  for (const item of items) {
    const categoryMatches = category === "" || item.category === category;
    const supplierMatches = supplier === "" || item.supplier_name === supplier;
    if (categoryMatches && supplierMatches) {
      shownItems.push(item);
    }
  }

  // recent movements table, or a message if there are none
  let movementsTable;
  if (movements.length === 0) {
    movementsTable = <p className="muted">No movements yet.</p>;
  } else {
    movementsTable = (
      <table>
        <thead>
          <tr><th>Date</th><th>Product</th><th>Type</th><th>Qty</th><th>Note</th></tr>
        </thead>
        <tbody>
          {movements.map((m) => (
            <tr key={m.id}>
              <td>{m.date}</td>
              <td>{m.name}</td>
              <td>{m.type}</td>
              <td>{m.quantity}</td>
              <td>{m.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  return (
    <div>
      <h2>Inventory</h2>

      <div className="panel">
        <h3>Add Stock Movement</h3>
        <p className="muted">
          Stock starts at the latest stock count in the dataset. Add IN when stock arrives and OUT when it is sold.
        </p>
        <form className="row" onSubmit={saveMovement}>
          <select value={productId} onChange={(e) => setProductId(e.target.value)}>
            {items.map((item) => (
              <option key={item.product_id} value={item.product_id}>
                {item.product_id} - {item.name}
              </option>
            ))}
          </select>

          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="IN">IN (stock received)</option>
            <option value="OUT">OUT (sold)</option>
          </select>

          <input type="number" placeholder="Quantity" required min="1"
            value={quantity} onChange={(e) => setQuantity(e.target.value)} />

          <input placeholder="Note (optional)"
            value={note} onChange={(e) => setNote(e.target.value)} />

          <button className="primary">Save</button>
        </form>
        <p>{message}</p>
      </div>

      <div className="panel">
        <div className="row">
          <h3 style={{ marginRight: "auto" }}>Products</h3>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">All categories</option>
            {categories.map((c) => <option key={c}>{c}</option>)}
          </select>
          <select value={supplier} onChange={(e) => setSupplier(e.target.value)}>
            <option value="">All suppliers</option>
            {suppliers.map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>

        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Product</th>
              <th>Category</th>
              <th>Supplier</th>
              <th>Price ($)</th>
              <th>Stock</th>
              <th>On Order</th>
              <th>Daily Demand</th>
              <th>Status</th>
              <th>Suggested Order</th>
            </tr>
          </thead>
          <tbody>
            {shownItems.map((item) => (
              <tr key={item.product_id}>
                <td>{item.product_id}</td>
                <td>{item.name}</td>
                <td>{item.category}</td>
                <td>{showValue(item.supplier_name)}</td>
                <td>{item.unit_price.toFixed(2)}</td>
                <td>{showValue(item.current_stock)}</td>
                <td>{item.on_order_qty}</td>
                <td>{item.avg_daily_demand}</td>
                <td><StatusBadge status={item.status} /></td>
                <td>{item.suggested_order_qty}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h3>Recent Stock Movements</h3>
        {movementsTable}
      </div>
    </div>
  );
}
