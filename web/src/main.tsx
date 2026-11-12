import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { applyAccent } from "./theme";
import "./styles/base.css";
import "./styles/calendar.css";
// 좁은 화면 줄바꿈. 덮어쓰기만 하므로 맨 마지막에 둔다.
import "./styles/responsive.css";

applyAccent();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
