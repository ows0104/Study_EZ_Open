import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { applyAccent } from "./theme";
import "./styles/base.css";
import "./styles/calendar.css";

applyAccent();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
