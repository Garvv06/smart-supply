// Member 4 - Main app. A sidebar on the left and one page on the right.
import { useState } from "react";
import Dashboard from "./pages/Dashboard";
import Inventory from "./pages/Inventory";
import Forecast from "./pages/Forecast";
import Assistant from "./pages/Assistant";

const pageNames = ["Dashboard", "Inventory", "Forecast", "Document Assistant"];

export default function App() {
  const [page, setPage] = useState("Dashboard");

  // decide which page to show
  let currentPage;
  if (page === "Dashboard") {
    currentPage = <Dashboard />;
  } else if (page === "Inventory") {
    currentPage = <Inventory />;
  } else if (page === "Forecast") {
    currentPage = <Forecast />;
  } else {
    currentPage = <Assistant />;
  }

  // make one button for each page, the selected one gets the "active" style
  const buttons = [];
  for (const name of pageNames) {
    let buttonClass = "nav";
    if (name === page) {
      buttonClass = "nav active";
    }
    buttons.push(
      <button key={name} className={buttonClass} onClick={() => setPage(name)}>
        {name}
      </button>
    );
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>SmartSupply AI</h1>
        {buttons}
      </aside>
      <main className="content">{currentPage}</main>
    </div>
  );
}
