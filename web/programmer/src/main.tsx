import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { installFetchAuth } from "./api/auth";
import "./styles/global.css";

// Patch fetch to add Authorization headers from stored credentials before
// any module makes a request (App.tsx already calls fetch on mount).
installFetchAuth();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
