import React from "react";
import { createRoot } from "react-dom/client";
import { BankResponseInput } from "../src/bank/BankResponseInput";
import "../src/styles/base.css";
import "../src/styles/calendar.css";

createRoot(document.getElementById("root")!).render(<BankResponseInput subject="약리학" runId="261016_03"
  disabled={false} onSaved={() => { document.body.dataset.saved = "yes"; }} />);
