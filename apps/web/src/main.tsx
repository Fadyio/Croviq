import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

if (typeof window !== "undefined") {
  const path = window.location.pathname;
  if (
    path.startsWith("/app/performance") ||
    path.startsWith("/app/experiments") ||
    path.startsWith("/app/overview")
  ) {
    window.history.replaceState(null, "", "/app");
  }
}

const rootElement = document.getElementById("root");

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}
