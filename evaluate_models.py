import json
import requests
from pathlib import Path
from statistics import mean

# --- Function to run model via Ollama API ---
def run_ollama(model: str, prompt: str) -> str:
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()["response"]
    except requests.exceptions.RequestException as e:
        print(f"❌ Error calling Ollama API for model {model}: {e}")
        raise

# --- Load files ---
prompts = Path("prompts.txt").read_text(encoding="utf-8").splitlines()
models = Path("models.txt").read_text(encoding="utf-8").splitlines()
judge_model = Path("judge.txt").read_text(encoding="utf-8").strip()

results = {model: [] for model in models}
scores = {model: [] for model in models}

# --- Run prompts on all models ---
for model in models:
    for prompt in prompts:
        print(f"▶️ Running prompt on model {model}...")
        response = run_ollama(model, prompt)
        results[model].append({"prompt": prompt, "response": response})

# --- Evaluate with judge model ---
evaluations = []
for prompt in prompts:
    answers = {
        m: next(r["response"] for r in results[m] if r["prompt"] == prompt)
        for m in models
    }
    evaluation_prompt = f"""
You are an evaluator. Compare the responses for the following prompt:

PROMPT: {prompt}

Responses:
{json.dumps(answers, indent=2, ensure_ascii=False)}

For each model, assign a score from 1 to 5 considering clarity, correctness, and completeness.
In the end, indicate which model responded best.
Expected format:

Scores: 

Model1: <score>
Average: <average score>

Model2: <score>
Average: <average score>

Best: <model name>

"""
    
print(f"⚖️ Evaluating prompt responses with {judge_model}...")
judge_response = run_ollama(judge_model, evaluation_prompt)

evaluations.append({"prompt": prompt, "evaluation": judge_response})

# --- Generate Markdown report ---
report = ["# Model Evaluation Report\n"]

for prompt in prompts:
    report.append(f"## Prompt\n```\n{prompt}\n```")
    for model in models:
        resp = next(r["response"] for r in results[model] if r["prompt"] == prompt)
        report.append(f"### Model: `{model}`\n{resp}\n")
    ev = next(e for e in evaluations if e["prompt"] == prompt)["evaluation"]
    report.append("### Evaluation\n")
    report.append(ev)

# --- Final ranking ---
# report.append("# Final Ranking\n")
# for i, (model, avg) in enumerate(ranking, 1):
#     scores_str = ", ".join(str(s) for s in scores[model]) if scores[model] else "no scores"
#     report.append(f"{i}. **{model}** — Average: {avg:.2f} | Scores: [{scores_str}]")

Path("report.md").write_text("\n\n".join(report), encoding="utf-8")

print("✅ Report generated in report.md")
