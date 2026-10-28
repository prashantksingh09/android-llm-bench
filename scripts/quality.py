"""Ask 20 fixed questions to the model loaded in llama-server and auto-grade the answers.

Usage: python ~/lab/scripts/quality.py MODEL.gguf     (llama-server must already be starting on port 8080)
Writes ~/lab/results/quality_<model>.csv
Short answers are graded automatically. Long answers are flagged needs_review=1:
read them and put 1 (right) or 0 (wrong) in their empty 'correct' cell.
"""
import csv
import json
import os
import re
import sys
import time
import urllib.request

URL = "http://127.0.0.1:8080"
SYSTEM = "Answer with only the final answer: a number, a word or a short phrase. No explanation."

QUESTIONS = [
    # (category, question, accepted answers)
    ("math", "What is 17 × 23?", ["391"]),
    ("math", "What is 144 divided by 12?", ["12"]),
    ("math", "A shirt costs 800 rupees and is discounted by 25%. What is the new price in rupees?", ["600"]),
    ("math", "What is 2 to the power of 10?", ["1024", "1 024"]),
    ("math", "A train travels 180 km in 2 hours. What is its average speed in km/h?", ["90"]),
    ("fact", "What is the chemical symbol for sodium?", ["na"]),
    ("fact", "Which planet in our solar system has the most mass?", ["jupiter"]),
    ("fact", "At sea level, what is the boiling point of water in degrees Celsius?", ["100"]),
    ("fact", "Who wrote the play Romeo and Juliet?", ["shakespeare"]),
    ("fact", "What is the SI unit of electric current?", ["ampere", "amperes", "amp", "amps"]),
    ("logic", "Tom is taller than Sam. Sam is taller than Ravi. Who is the shortest?", ["ravi"]),
    ("logic", "If today is Monday, what day of the week will it be 10 days from now?", ["thursday"]),
    ("logic", "A farmer has 15 sheep. All but 8 run away. How many sheep are left?", ["8", "eight"]),
    ("logic", "What is the next number in the sequence 2, 6, 12, 20, 30?", ["42"]),
    ("logic", "All bloops are razzies and all razzies are lazzies. Are all bloops lazzies? Answer yes or no.", ["yes"]),
    ("language", "Reverse the letters of the word planet.", ["tenalp"]),
    ("language", "What is the opposite of the word ancient?", ["modern", "new"]),
    ("language", "How many letters are in the word physics?", ["7", "seven"]),
    ("language", "Translate 'thank you' into French.", ["merci"]),
    ("science", "Which gas do plants take in from the air for photosynthesis?", ["carbon dioxide", "co2"]),
]


def norm(s):
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s.lower()).split())


def matches(response, answers):
    text = f" {norm(response)} "
    return any(f" {norm(a)} " in text for a in answers)


def wait_for_server(timeout=600):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(URL + "/health", timeout=5) as r:
                if r.status == 200:
                    return
        except Exception:
            pass
        time.sleep(2)
    raise SystemExit("llama-server did not become ready - check ~/lab/results/server.log")


def ask(question):
    body = json.dumps({
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}],
        "temperature": 0,
        "seed": 42,
        "max_tokens": 64,
    }).encode()
    req = urllib.request.Request(URL + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        res = json.load(r)
    text = (res["choices"][0]["message"].get("content") or "").strip()
    tps = res.get("timings", {}).get("predicted_per_second")
    return text, tps


model = sys.argv[1]
name = os.path.basename(model).removesuffix(".gguf")
out_path = os.path.expanduser(f"~/lab/results/quality_{name}.csv")
print(f"waiting for llama-server ({name})...")
wait_for_server()

auto_right = auto_total = review = 0
with open(out_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "category", "question", "expected", "response",
                "auto_match", "needs_review", "correct", "gen_tok_per_s"])
    for i, (cat, q, answers) in enumerate(QUESTIONS, 1):
        text, tps = ask(q)
        hit = int(matches(text, answers))
        long_answer = int(len(norm(text).split()) > 8)
        correct = "" if long_answer else hit
        if long_answer:
            review += 1
        else:
            auto_total += 1
            auto_right += hit
        w.writerow([i, cat, q, " | ".join(answers), text, hit, long_answer, correct,
                    round(tps, 2) if tps else ""])
        flag = "REVIEW" if long_answer else ("ok" if hit else "WRONG")
        print(f"{i:2}. [{flag:6}] {text[:70]!r}")

print(f"\n{name}: {auto_right}/{auto_total} right among short answers, {review} to review by hand")
print(f"saved {out_path}")
