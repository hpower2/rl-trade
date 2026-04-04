import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import { installManualWalkthroughRuntime } from "./mock-operator/runtime";

installManualWalkthroughRuntime();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
