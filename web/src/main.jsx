import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import FaixaRascunho from "./piloto/FaixaRascunho";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <FaixaRascunho />
    <App />
  </React.StrictMode>
);
