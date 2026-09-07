import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { Router } from "./router";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Router>
      <App />
    </Router>
  </StrictMode>,
);
