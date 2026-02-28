import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Toaster } from "sonner";
import "./globals.css";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
    <Toaster
      theme="dark"
      position="bottom-right"
      toastOptions={{
        style: {
          background: "oklch(0.18 0 0)",
          border: "1px solid oklch(1 0 0 / 8%)",
          color: "oklch(0.95 0 0)",
        },
      }}
    />
  </StrictMode>,
);
