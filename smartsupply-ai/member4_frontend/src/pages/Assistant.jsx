// Document Assistant page: ask questions about the product reports (made from the dataset)
// and any documents the user uploads
import { useEffect, useState } from "react";
import { api } from "../api";

const exampleQuestions = [
  "Which category has the highest sales?",
  "Which products sold the most?",
  "What period does the sales data cover?",
];

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

  useEffect(() => {
    api.documents().then((result) => setDocuments(result));
  }, []);

  async function ask(text) {
    if (text.trim() === "") {
      return;
    }
    setLoading(true);
    const result = await api.ask(text);

    const newMessage = {
      question: text,
      answer: result.answer,
      sources: result.sources,
    };
    setChat(chat.concat([newMessage]));
    setQuestion("");
    setLoading(false);
  }

  async function uploadFile(e) {
    const file = e.target.files[0];
    if (!file) {
      return;
    }
    await api.upload(file);
    api.documents().then((result) => setDocuments(result));
    e.target.value = "";
  }

  // before the first question, show some example questions
  let emptyMessage = null;
  if (chat.length === 0) {
    emptyMessage = (
      <div className="muted">
        Ask about any product or the store sales. You can also upload your own documents. Try:
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
          <h3>Documents</h3>
          <ul className="doc-list">
            {documents.map((d) => <li key={d}>{d}</li>)}
          </ul>
          <label className="upload">
            + Upload .txt or .pdf
            <input type="file" accept=".txt,.pdf" onChange={uploadFile} hidden />
          </label>
        </div>
      </div>
    </div>
  );
}
