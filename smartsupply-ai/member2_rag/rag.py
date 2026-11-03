# Member 2 - Document Assistant using RAG (Retrieval-Augmented Generation)
#
# The documents are:
#   - product reports and a store summary made from the Kaggle dataset
#     (data/load_kaggle_data.py writes them into data/documents)
#   - any .txt or .pdf the user uploads in the app (contracts, invoices, policies...)
#
# Steps:
#   1. Load     - read all documents in the documents folder (.txt or .pdf)
#   2. Chunk    - break each document into small paragraphs
#   3. Embed    - turn every paragraph into numbers using TF-IDF
#   4. Retrieve - when a question comes, find the paragraphs most similar to it
#   5. Answer   - give the answer from those paragraphs and show which file it came from
#
# Why RAG? The answer always comes from our own documents and we show the source,
# so the user can check it. If nothing matches, we say "not found" instead of guessing.
#
# No internet or API key is needed. The answer is the best matching paragraph.
# Optional: if you set LLM_API_KEY, an LLM writes the answer in nicer words,
# but it is only given the paragraphs we found.
#
# Run:  python rag.py   (asks some test questions and checks accuracy)

import os
import sys
import json
import urllib.request
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS_FOLDER = os.path.join(HERE, "..", "data", "documents")
MIN_SCORE = 0.10   # if the best match scores less than this, we say "not found"


class DocumentAssistant:

    def __init__(self, folder=DOCS_FOLDER):
        self.folder = folder
        self.build_index()

    def read_file(self, path):
        if path.endswith(".pdf"):
            from pypdf import PdfReader
            reader = PdfReader(path)
            text = ""
            for page in reader.pages:
                text = text + page.extract_text() + "\n\n"
            return text

        with open(path, encoding="utf-8") as f:
            return f.read()

    def build_index(self):
        # Step 1 and 2: read every document and split it into paragraphs
        self.chunks = []
        for file_name in sorted(os.listdir(self.folder)):
            if not (file_name.endswith(".txt") or file_name.endswith(".pdf")):
                continue

            text = self.read_file(os.path.join(self.folder, file_name))
            title = text.strip().split("\n")[0]   # first line is the document title

            # a blank line means a new paragraph
            for paragraph in text.split("\n\n"):
                paragraph = paragraph.strip()
                if len(paragraph) > 30:
                    # we add the title to each paragraph so it knows which document it is from
                    self.chunks.append({"source": file_name, "text": title + "\n" + paragraph})

        # if there are no documents yet, there is nothing to search
        if len(self.chunks) == 0:
            return

        # Step 3: turn every paragraph into a TF-IDF vector
        all_texts = []
        for chunk in self.chunks:
            all_texts.append(chunk["text"])

        # token_pattern: also keep 1-letter words like "V" in "Grand Theft Auto V" or "3"
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2),
                                          token_pattern=r"(?u)\b\w+\b")
        self.vectors = self.vectorizer.fit_transform(all_texts)

    def search(self, question, top_k=3):
        # Step 4: compare the question with every paragraph
        question_vector = self.vectorizer.transform([question])
        scores = cosine_similarity(question_vector, self.vectors)[0]

        # indexes of the highest scores first
        best_indexes = scores.argsort()[::-1][:top_k]

        results = []
        for i in best_indexes:
            results.append({
                "source": self.chunks[i]["source"],
                "text": self.chunks[i]["text"],
                "score": round(float(scores[i]), 3),
            })
        return results

    def ask(self, question):
        if len(self.chunks) == 0:
            return {
                "answer": "No documents yet. Run load_kaggle_data.py or upload a document.",
                "sources": [],
                "grounded": False,
            }

        results = self.search(question)

        # If even the best paragraph is not similar enough, we don't guess
        if results[0]["score"] < MIN_SCORE:
            return {
                "answer": "I could not find this in the uploaded documents.",
                "sources": [],
                "grounded": False,
            }

        # keep only the paragraphs that are similar enough
        relevant = []
        for r in results:
            if r["score"] >= MIN_SCORE:
                relevant.append(r)

        # Step 5: make the answer
        if os.getenv("LLM_API_KEY"):
            answer = self.llm_answer(question, relevant)
        else:
            answer = self.simple_answer(relevant[0]["text"])

        return {"answer": answer, "sources": relevant, "grounded": True}

    def simple_answer(self, text):
        # return the best paragraph, without the title line we added
        lines = text.split("\n")
        return "\n".join(lines[1:])

    def llm_answer(self, question, results):
        # Optional: send the found paragraphs to an LLM (any OpenAI-style API)
        context = ""
        for r in results:
            context = context + "[" + r["source"] + "]\n" + r["text"] + "\n\n"

        prompt = ("Answer the question using ONLY the context below. "
                  "If the answer is not in the context, say you don't know.\n\n"
                  "Context:\n" + context + "\nQuestion: " + question)

        url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1") + "/chat/completions"
        body = {
            "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "Authorization": "Bearer " + os.getenv("LLM_API_KEY"),
            "Content-Type": "application/json",
        }
        request = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
        response = urllib.request.urlopen(request, timeout=30)
        data = json.loads(response.read())
        return data["choices"][0]["message"]["content"]


# ---------- Testing: does the search find the right document? ----------
# The test questions are made from the products in the dataset.
# For every product we ask about its price and its total sales,
# and the right answer is that product's report file.

def make_test_questions():
    tests = [
        ["Which category has the highest sales?", "store_summary.txt"],
        ["What period does the sales data cover?", "store_summary.txt"],
    ]

    products_file = os.path.join(HERE, "..", "data", "products.csv")
    if not os.path.exists(products_file):
        return tests

    import pandas as pd
    products = pd.read_csv(products_file, encoding="utf-8")
    for index, p in products.iterrows():
        report_file = "product_" + p["product_id"] + ".txt"
        tests.append(["What is the price of " + p["name"] + "?", report_file])
        tests.append(["How many units of " + p["name"] + " were sold in total?", report_file])
    return tests


def evaluate(assistant):
    tests = make_test_questions()
    correct = 0
    for test in tests:
        question = test[0]
        expected_file = test[1]
        found_file = assistant.search(question, top_k=1)[0]["source"]

        if found_file == expected_file:
            correct = correct + 1
            print("Correct |", question, "->", found_file)
        else:
            print("Wrong   |", question, "->", found_file, "(expected", expected_file + ")")

    total = len(tests)
    print()
    print("Retrieval accuracy:", correct, "/", total, "=", round(correct / total * 100), "%")


if __name__ == "__main__":
    bot = DocumentAssistant()
    print("Loaded", len(bot.chunks), "paragraphs from the documents.")
    print()
    if len(bot.chunks) == 0:
        print("No documents found. Run data/load_kaggle_data.py first.")
        sys.exit(1)

    sample_questions = [
        "Which category has the highest sales?",
        "Which products sold the most?",
        "What is the weather today?",
    ]
    for q in sample_questions:
        result = bot.ask(q)
        print("Q:", q)
        print("A:", result["answer"])
        source_files = []
        for s in result["sources"]:
            if s["source"] not in source_files:
                source_files.append(s["source"])
        print("Sources:", source_files)
        print()

    evaluate(bot)
