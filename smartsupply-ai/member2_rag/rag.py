# Member 2 - Document Assistant using RAG (Retrieval-Augmented Generation)
#
# The documents are in data/documents (data/load_data.py and forecast.py write them):
#   products/         - one report per product (price, supplier, lead time, stock, sales)
#   suppliers/        - one profile per supplier (credit rating, purchase history)
#   purchase_orders/  - purchase orders with their invoice amounts
#   contracts/        - real supply agreements from CUAD
#   policies/         - the inventory policy (reorder rules)
#   store_summary.txt - overall sales summary
#   uploads/          - any .txt or .pdf the user uploads in the app
#
# Steps:
#   1. Load     - read all documents in the documents folder and its subfolders (.txt or .pdf)
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
# Run:  python rag.py   (answers the test questions in data/evaluation_questions.csv and checks accuracy)

import os
import re
import sys
import json
import urllib.request
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
from sklearn.metrics.pairwise import cosine_similarity

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS_FOLDER = os.path.join(HERE, "..", "data", "documents")
QUESTIONS_FILE = os.path.join(HERE, "..", "data", "evaluation_questions.csv")
MIN_SCORE = 0.10   # if the best match scores less than this, we say "not found"
MAX_CHUNK_CHARS = 1500   # contracts have some very long paragraphs, we cut them into smaller pieces

# scikit-learn's English stop word list also removes words that matter in invoices and contracts,
# like "due" in "total due" or "not" and "within" in "not less than ... within 30 days". We keep them.
KEEP_WORDS = {"due", "amount", "bill", "part", "first", "last", "per", "less", "least", "most", "more",
              "never", "none", "not", "no", "without", "within", "after", "before", "until", "cannot"}
STOP_WORDS = sorted(ENGLISH_STOP_WORDS - KEEP_WORDS)

# A paragraph's score = how similar the paragraph is to the question
#                     + TITLE_WEIGHT x how similar its document title is to the question.
# The title helps find the right document (e.g. the contract name or the purchase order number),
# then the paragraph text decides which part of that document is the answer.
TITLE_WEIGHT = 0.5


def list_documents(folder=DOCS_FOLDER):
    # every .txt and .pdf in the folder and its subfolders, like "products/product_P001.txt"
    files = []
    for current_folder, sub_folders, file_names in os.walk(folder):
        sub_folders.sort()
        for file_name in sorted(file_names):
            if file_name.lower().endswith(".txt") or file_name.lower().endswith(".pdf"):
                relative = os.path.relpath(os.path.join(current_folder, file_name), folder)
                files.append(relative.replace("\\", "/"))   # same names on Windows and Linux
    return files


def split_long_paragraph(paragraph):
    # Cut a long paragraph into pieces of up to MAX_CHUNK_CHARS, at the end of a sentence.
    # A short paragraph comes back as it is.
    if len(paragraph) <= MAX_CHUNK_CHARS:
        return [paragraph]
    pieces = []
    current = ""
    for sentence in re.split(r"(?<=[.;:])\s+", paragraph):
        if current != "" and len(current) + len(sentence) > MAX_CHUNK_CHARS:
            pieces.append(current)
            current = ""
        current = (current + " " + sentence).strip()
    if current != "":
        pieces.append(current)
    return pieces


class DocumentAssistant:

    def __init__(self, folder=DOCS_FOLDER):
        self.folder = folder
        self.build_index()

    def read_file(self, path):
        if path.lower().endswith(".pdf"):
            from pypdf import PdfReader
            reader = PdfReader(path)
            text = ""
            for page in reader.pages:
                text = text + (page.extract_text() or "") + "\n\n"
            return text

        # errors="replace" so one uploaded file that is not UTF-8 does not stop the whole app
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def build_index(self):
        # Step 1 and 2: read every document and split it into paragraphs
        self.chunks = []
        for file_name in list_documents(self.folder):
            try:
                text = self.read_file(os.path.join(self.folder, file_name))
            except Exception as error:
                # for example a broken PDF: skip it, but keep the other documents
                print("Could not read", file_name, "-", error)
                continue
            if text.strip() == "":
                continue
            title = text.strip().split("\n")[0]   # first line is the document title

            # a blank line means a new paragraph
            for paragraph in text.split("\n\n"):
                paragraph = paragraph.strip()
                # skip very short paragraphs and the title line (it is added to every paragraph already)
                if len(paragraph) <= 30 or paragraph == title:
                    continue
                for piece in split_long_paragraph(paragraph):
                    # we add the title to each paragraph so it knows which document it is from
                    self.chunks.append({"source": file_name, "title": title, "text": title + "\n" + piece})

        # if there are no documents yet, there is nothing to search
        if len(self.chunks) == 0:
            return

        # Step 3: turn every paragraph (and its document title) into a TF-IDF vector
        all_texts = []
        all_titles = []
        for chunk in self.chunks:
            all_texts.append(chunk["text"])
            all_titles.append(chunk["title"])

        # token_pattern: also keep 1-letter words and numbers like "4" in "Hitch Rack - 4-Bike"
        self.vectorizer = TfidfVectorizer(stop_words=STOP_WORDS, ngram_range=(1, 2),
                                          token_pattern=r"(?u)\b\w+\b")
        self.vectors = self.vectorizer.fit_transform(all_texts)
        self.title_vectors = self.vectorizer.transform(all_titles)

    def search(self, question, top_k=3):
        # Step 4: compare the question with every paragraph and with its document title
        question_vector = self.vectorizer.transform([question])
        text_scores = cosine_similarity(question_vector, self.vectors)[0]
        title_scores = cosine_similarity(question_vector, self.title_vectors)[0]
        scores = text_scores + TITLE_WEIGHT * title_scores

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
                "answer": "No documents yet. Run data/load_data.py or upload a document.",
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
        answer = self.simple_answer(relevant[0]["text"])
        if os.getenv("LLM_API_KEY"):
            try:
                answer = self.llm_answer(question, relevant)
            except Exception as error:
                # no internet or a wrong key: keep the best paragraph as the answer
                print("LLM call failed, using the best paragraph instead -", error)

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


# ---------- Testing: does the search find the right document and the right answer? ----------
# The test questions are in data/evaluation_questions.csv (data/load_data.py makes them).
# Every question has the file that holds the answer and the answer itself:
#   - products, suppliers, purchase orders: the answer is a number or name from the dataset
#   - contracts: the answer is the clause that lawyers marked in CUAD
# We check 4 things:
#   1. Top-1 source   - the best paragraph comes from the right file
#   2. Top-3 source   - one of the 3 paragraphs we show comes from the right file
#   3. Answer in best - the right answer is written in the best paragraph
#                       (this is the answer the user sees when no LLM is used)
#   4. Answer in top3 - the right answer is written in one of the 3 paragraphs we show
#                       (this is what an LLM would be given, so the answer is supported by the sources)
# We also ask questions that are NOT in the documents. The right reply is "not found".

OUT_OF_SCOPE_QUESTIONS = [
    "What is the weather today?",
    "Who won the football world cup?",
    "How do I cook pasta?",
    "What is the capital of France?",
    "Tell me a joke",
]


def normalize(text):
    # lower case and single spaces, so line breaks do not change the result
    return " ".join(str(text).lower().split())


def answer_is_in(expected_answer, retrieved_text):
    # A contract clause can have more than one marked answer, they are split by " || ".
    # Long clauses can be cut between two paragraphs, so we check the first 100 characters.
    retrieved_text = normalize(retrieved_text)
    for answer in str(expected_answer).split(" || "):
        answer = normalize(answer)[:100]
        if answer != "" and answer in retrieved_text:
            return True
    return False


def evaluate(assistant):
    import pandas as pd
    if not os.path.exists(QUESTIONS_FILE):
        print("No test questions. Run data/load_data.py first.")
        return

    tests = pd.read_csv(QUESTIONS_FILE, encoding="utf-8")
    rows = []
    for index, test in tests.iterrows():
        results = assistant.search(test["question"], top_k=3)
        sources = []
        retrieved_text = ""
        for r in results:
            sources.append(r["source"])
            retrieved_text = retrieved_text + r["text"] + "\n"
        rows.append({
            "group": test["group"],
            "question": test["question"],
            "expected_source": test["expected_source"],
            "found_source": sources[0],
            "top1_source": sources[0] == test["expected_source"],
            "top3_source": test["expected_source"] in sources,
            "answer_in_best": answer_is_in(test["expected_answer"], results[0]["text"]),
            "answer_in_top3": answer_is_in(test["expected_answer"], retrieved_text),
        })
    results_table = pd.DataFrame(rows)
    checks = ["top1_source", "top3_source", "answer_in_best", "answer_in_top3"]

    # Out of scope questions: the assistant should say "not found"
    refused = 0
    for question in OUT_OF_SCOPE_QUESTIONS:
        if not assistant.ask(question)["grounded"]:
            refused = refused + 1

    summary = results_table.groupby("group")[checks].mean() * 100
    summary["questions"] = results_table.groupby("group").size()
    summary.loc["All"] = list(results_table[checks].mean() * 100) + [len(results_table)]
    summary = summary.round(1)
    summary["questions"] = summary["questions"].astype(int)

    print("Document assistant test (" + str(len(results_table)) + " questions, % correct):")
    print(summary.to_string())
    print()
    print("Out of scope questions answered with \"not found\":", refused, "/", len(OUT_OF_SCOPE_QUESTIONS))

    output_folder = os.path.join(HERE, "output")
    os.makedirs(output_folder, exist_ok=True)
    results_table.to_csv(os.path.join(output_folder, "rag_evaluation.csv"), index=False)
    summary.to_csv(os.path.join(output_folder, "rag_summary.csv"))
    print("Results for every question are in member2_rag/output/rag_evaluation.csv")


if __name__ == "__main__":
    bot = DocumentAssistant()
    print("Loaded", len(bot.chunks), "paragraphs from", len(list_documents()), "documents.")
    print()
    if len(bot.chunks) == 0:
        print("No documents found. Run data/load_data.py first.")
        sys.exit(1)

    sample_questions = [
        "Who supplies the AWC Logo Cap?",
        "What is the reorder point rule?",
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
