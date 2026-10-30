import json
import re
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = PROJECT_ROOT / "accounts" / "templates" / "flask"
STATIC_DIR = PROJECT_ROOT / "accounts" / "static"
KNOWLEDGE_PATH = PROJECT_ROOT / "accounts" / "data" / "chat_knowledge.json"

with KNOWLEDGE_PATH.open(encoding="utf-8") as knowledge_file:
    KNOWLEDGE = json.load(knowledge_file)

app = Flask(
    __name__,
    template_folder=str(TEMPLATE_DIR),
    static_folder=None,
)


def _normalize(value):
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def answer_question(question):
    normalized_question = _normalize(question)
    matches = []
    for intent in KNOWLEDGE["intents"]:
        for alias in intent["aliases"]:
            normalized_alias = _normalize(alias)
            if f" {normalized_alias} " in f" {normalized_question} ":
                matches.append((len(normalized_alias), intent["id"]))
    if matches:
        _, intent_id = max(matches)
        answer = KNOWLEDGE["answers"].get(intent_id)
        if answer:
            return answer
    return KNOWLEDGE["unknown_answer"]


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/static/<path:filename>")
def static(filename):
    return send_from_directory(STATIC_DIR, filename)


@app.post("/api/answer")
def answer():
    payload = request.get_json(silent=True)
    question = payload.get("question") if isinstance(payload, dict) else None
    if not isinstance(question, str) or not question.strip():
        return jsonify({"error": "Enter a question to get an answer."}), 400
    if len(question) > 500:
        return jsonify({"error": "Questions must be 500 characters or fewer."}), 400
    return jsonify({"answer": answer_question(question)})
