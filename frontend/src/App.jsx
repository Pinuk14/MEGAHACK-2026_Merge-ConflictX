import { useState, useEffect } from "react";
import FormulaAI from "./pages/Simulation";
import GPProtocol from "./pages/Chatbot";

export default function App() {
  const [testReact, setTestReact] = useState(true);
  const [view, setView] = useState("dashboard");
  const [chatSeedFileIds, setChatSeedFileIds] = useState([]);

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

  if (view === "chatbot") {
    return (
      <GPProtocol
        initialFileIds={chatSeedFileIds}
        onBack={() => setView("dashboard")}
      />
    );
  }

  return (
    <FormulaAI
      onOpenChatbot={(payload) => {
        setChatSeedFileIds(Array.isArray(payload?.fileIds) ? payload.fileIds : []);
        setView("chatbot");
      }}
    />
  );
}
