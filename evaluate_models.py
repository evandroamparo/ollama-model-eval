import json
import requests
from pathlib import Path
from statistics import mean

# --- Function to run model via Ollama API ---
def run_ollama(model: str, prompt: str) -> str:
    """
    Calls the Ollama API with streaming enabled and prints the response
    in real time. Returns the full response string.
    """
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True
    }
    try:
        # Enable streaming of the response
        with requests.post(url, json=payload, stream=True) as response:
            response.raise_for_status()
            full_response = ""
            mode =  "" ## thinking or response
            for line in response.iter_lines(decode_unicode=True, chunk_size=8192):  # Add decode_unicode
                if line:
                    try:
                        data = json.loads(line)
                        thinking_chunk = data.get("thinking", "")
                        response_chunk = data.get("response", "")
                        # print mode indicator only when it changes
                        if thinking_chunk and mode != "thinking":
                            mode = "thinking"
                            print("\n🤔 Thinking...\n", end="", flush=True)
                        elif response_chunk and mode != "response":
                            mode = "response"
                            print("\n💬 Response:\n", end="", flush=True)

                        chunk = thinking_chunk or response_chunk
                        print(chunk, end="", flush=True)
                        # only include response chunks in the final response
                        if response_chunk:
                            full_response += response_chunk
                    except json.JSONDecodeError as e:
                        print(f"⚠️ JSONDecodeError: {e} - Line: {line}")
                        # Consider adding a way to handle or log the invalid JSON
            print()
            return full_response
    except requests.exceptions.RequestException as e:
        print(f"❌ Error calling Ollama API for model {model}: {e}")
        return "RequestError"  # Or handle other request errors

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

# Build comprehensive evaluation prompt with ALL prompts and responses
all_evaluations = ""
for prompt in prompts:
    answers = {
        m: next(r["response"] for r in results[m] if r["prompt"] == prompt)
        for m in models
    }
    all_evaluations += f"""
### PROMPT: {prompt}

Responses:
{json.dumps(answers, indent=2, ensure_ascii=False)}

---

"""

comprehensive_evaluation_prompt = f"""
You are an evaluator. Compare the responses for the following prompts:

{all_evaluations}

For for each model, assign a score from 1 to 5 considering clarity, correctness, and completeness.
In the end, indicate which model responded best overall.
Expected format:

Scores:

<model name>: 
Clarity: <score> and reasoning
Correctness: <score> and reasoning
Completeness: <score> and reasoning
Average: <average score>

[Repeat for each model]

**Overall Best Model: <model name>**
"""

print(f"⚖️ Evaluating all prompt responses with {judge_model}...")
judge_response = run_ollama(judge_model, comprehensive_evaluation_prompt)
evaluations.append({"prompt": "all", "evaluation": judge_response})

# --- Generate Markdown report ---
report = ["# Model Evaluation Report\n"]

for prompt in prompts:
    report.append(f"## Prompt\n```\n{prompt}\n```")
    for model in models:
        resp = next(r["response"] for r in results[model] if r["prompt"] == prompt)
        report.append(f"### Model: `{model}`\n{resp}\n")

# Add the comprehensive evaluation at the end
report.append("## Evaluation\n")
overall_evaluation = next(e for e in evaluations if e["prompt"] == "all")["evaluation"]
report.append(overall_evaluation)

# --- Final ranking ---
# report.append("# Final Ranking\n")
# for i, (model, avg) in enumerate(ranking, 1):
#     scores_str = ", ".join(str(s) for s in scores[model]) if scores[model] else "no scores"
#     report.append(f"{i}. **{model}** — Average: {avg:.2f} | Scores: [{scores_str}]")

Path("report.md").write_text("\n\n".join(report), encoding="utf-8")

print("✅ Report generated in report.md")
