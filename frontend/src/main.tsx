import React, { Component, type ErrorInfo, type ReactNode } from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "leaflet/dist/leaflet.css";
import "./index.css";

class RootErrorBoundary extends Component<{ children: ReactNode }, { err: Error | null }> {
  state = { err: null as Error | null };

  static getDerivedStateFromError(err: Error) {
    return { err };
  }

  componentDidCatch(err: Error, info: ErrorInfo) {
    console.error(err, info);
  }

  render() {
    if (this.state.err) {
      return (
        <div style={{ padding: "1.5rem", fontFamily: "system-ui, sans-serif" }}>
          <h1 style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>
            Something went wrong loading the app.
          </h1>
          <pre
            style={{
              fontSize: "12px",
              overflow: "auto",
              background: "#f4f4f4",
              padding: "12px",
              borderRadius: 8,
              whiteSpace: "pre-wrap",
            }}
          >
            {this.state.err.message}
          </pre>
          <p style={{ fontSize: "13px", color: "#555", marginTop: "1rem" }}>
            Open DevTools Console for the full stack trace (F12 → Console).
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RootErrorBoundary>
      <App />
    </RootErrorBoundary>
  </React.StrictMode>,
);
