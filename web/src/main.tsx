import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { applyToDocument, useSettings } from "./state/settings";
import "./styles/index.css";

applyToDocument(useSettings.getState());
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
