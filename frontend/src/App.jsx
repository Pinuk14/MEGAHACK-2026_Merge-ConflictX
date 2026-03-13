import { useState, useEffect } from "react";
import FormulaAI from "./pages/Simulation";

export default function App() {
  const [testReact, setTestReact] = useState(true);

  useEffect(() => {
    console.log("React is working!");
  }, []);

  if (!testReact) {
    return (
      <div style={{ padding: "20px", color: "white", background: "#000" }}>
        <h1>Test ComponentLoading...</h1>
      </div>
    );
  }

  return <FormulaAI />;
}
