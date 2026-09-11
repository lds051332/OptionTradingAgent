import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { LocaleProvider } from "./locale";
import { Router } from "./router";
import { applyHeadIcons } from "./staticMedia";
import "./index.css";

applyHeadIcons();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <LocaleProvider>
      <Router>
        <App />
      </Router>
    </LocaleProvider>
  </StrictMode>,
);
