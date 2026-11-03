// Document Assistant page: ask questions about the product reports, supplier profiles,
// purchase orders, supply contracts and inventory policy, and any documents the user uploads
import { useEffect, useState } from "react";
import { api } from "../api";

const exampleQuestions = [
  "What is the lead time for the Water Bottle - 30 oz.?",
  "What was the total due for purchase order 4001?",
  "What is the credit rating of Green Lake Bike Company?",
  "How is safety stock calculated?",
];

// "contracts/contract_VERICELCORP.txt" -> "contracts", "store_summary.txt" -> ""
function folderOf(path) {
  const slash = path.lastIndexOf("/");
  if (slash === -1) {
    return "";
  }
  return path.substring(0, slash);
}

// count the documents in each folder, e.g. { "contracts": 24, "products": 20 }
function countByFolder(documents) {
  const counts = {};
  for (const d of documents) {
    const folder = folderOf(d);
    if (folder !== "" && folder !== "uploads") {
      counts[folder] = (counts[folder] || 0) + 1;
    }
  }
  return counts;
}

// the same file can come up more than once, so we keep each name only once
function getSourceNames(sources) {
  const names = [];
  for (const s of sources) {
    if (!names.includes(s.source)) {
      names.push(s.source);
    }
  }
  return names.join(", ");
}

export default function Assistant() {
  const [question, setQuestion] = useState("");
  const [chat, setChat] = useState([]);   // list of { question, answer, sources }
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");

  function loadDocuments() {
    api.documents()
      .then((result) => setDocuments(result))
      .catch((err) => setUploadMessage("Cannot reach backend: " + err.message));
  }

  useEffect(() => {
    loadDocuments();
  }, []);

  async function ask(text) {
    if (text.trim() === "") {
      return;
    }
    setLoading(true);
    let newMessage;
    try {
      const result = await api.ask(text);
      newMessage = { question: text, answer: result.answer, sources: result.sources };
    } catch (err) {
      newMessage = { question: text, answer: "Error: " + err.message, sources: [] };
    }
    // use the latest chat, in case two questions were asked quickly
    setChat((oldChat) => oldChat.concat([newMessage]));
    setQuestion("");
    setLoading(false);
  }

  async function uploadFile(e) {
    const file = e.target.files[0];
    if (!file) {
      return;
    }
    try {
      const result = await api.upload(file);
      setUploadMessage(result.message);
      loadDocuments();
    } catch (err) {
      setUploadMessage("Error: " + err.message);
    }
    e.target.value = "";
  }

  const folderCounts = countByFolder(documents);
  const otherDocuments = [];   // documents that are not in a dataset folder, like uploads
  for (const d of documents) {
    const folder = folderOf(d);
    if (folder === "" || folder === "uploads") {
      otherDocuments.push(d);
    }
  }

  // before the first question, show some example questions
  let emptyMessage = null;
  if (chat.length === 0) {
    emptyMessage = (
      <div className="muted">
        Ask about products, suppliers, purchase orders, supply contracts or the inventory policy.
        You can also upload your own documents. Try:
        {exampleQuestions.map((q) => (
          <button key={q} className="example" onClick={() => ask(q)}>{q}</button>
        ))}
      </div>
    );
  }

  let loadingText = null;
  if (loading) {
    loadingText = <p className="muted">Searching documents...</p>;
  }

  return (
    <div>
      <h2>Document Assistant</h2>

      <div className="grid-2 wide-left">
        <div className="panel">
          <div className="chat">
            {emptyMessage}

            {chat.map((c, index) => {
              let sourcesLine = null;
              if (c.sources.length > 0) {
                sourcesLine = <div className="sources">Sources: {getSourceNames(c.sources)}</div>;
              }
              return (
                <div key={index}>
                  <div className="bubble user">{c.question}</div>
                  <div className="bubble bot">
                    {c.answer}
                    {sourcesLine}
                  </div>
                </div>
              );
            })}

            {loadingText}
          </div>

          <form className="row" onSubmit={(e) => { e.preventDefault(); ask(question); }}>
            <input style={{ flex: 1 }} placeholder="Type your question..."
              value={question} onChange={(e) => setQuestion(e.target.value)} />
            <button className="primary">Ask</button>
          </form>
        </div>

        <div className="panel">
          <h3>Documents ({documents.length})</h3>
          <ul className="doc-list">
            {Object.keys(folderCounts).map((folder) => (
              <li key={folder}>
                {folder.replace("_", " ")}: {folderCounts[folder]} {folderCounts[folder] === 1 ? "file" : "files"}
              </li>
            ))}
            {otherDocuments.map((d) => <li key={d}>{d}</li>)}
          </ul>
          <label className="upload">
            + Upload .txt or .pdf
            <input type="file" accept=".txt,.pdf" onChange={uploadFile} hidden />
          </label>
          <p className="muted">{uploadMessage}</p>
        </div>
      </div>
    </div>
  );
}
