import json
import requests
import os
import time
from pathlib import Path
from statistics import mean
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

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

# --- Function to run model via OpenAI API ---
def run_openai(model: str, prompt: str) -> str:
    """
    Calls the OpenAI API and streams the response.
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    full_response = ""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=True  # Enable streaming
        )
        for chunk in response:
            if chunk.choices:
                delta = chunk.choices[0].delta
                chunk_content = getattr(delta, 'content', '') or ''
                print(chunk_content, end="", flush=True)  # Print the chunk in real-time
                full_response += chunk_content
        print()  # New line after the response
        return full_response
    except Exception as e:
        print(f"❌ Error calling OpenAI API for model {model}: {e}")
        return "RequestError"

# --- Load files ---
prompts = Path("prompts.txt").read_text(encoding="utf-8").splitlines()
models = Path("models.txt").read_text(encoding="utf-8").splitlines()
judge_model = Path("judge.txt").read_text(encoding="utf-8").strip()

results = {model: [] for model in models}
scores = {model: [] for model in models}

def calculate_time_scores(models_results: dict) -> dict:
    """
    Calculate normalized time scores (1-5) based on relative performance.
    Fastest model gets 5, slowest gets 1, others interpolated.
    This ensures fair comparison regardless of absolute times.
    """
    # Calculate total time per model
    model_times = {m: sum(r["time"] for r in results[m]) for m in models_results}

    if not model_times:
        return {}

    fastest = min(model_times.values())
    slowest = max(model_times.values())

    time_scores = {}
    for model, total_time in model_times.items():
        if fastest == slowest:
            # All models had same time
            time_scores[model] = 5.0
        else:
            # Interpolate: fastest=5, slowest=1
            normalized = (slowest - total_time) / (slowest - fastest)
            time_scores[model] = 1 + (normalized * 4)  # Scale to 1-5 range

    return time_scores

# --- Run prompts on all models ---
for model in models:
    for prompt in prompts:
        print(f"▶️ Running prompt on model {model}...")
        start_time = time.perf_counter()
        response = run_ollama(model, prompt)
        elapsed_time = time.perf_counter() - start_time
        print(f"⏱️ Completed in {elapsed_time:.2f}s\n")
        results[model].append({"prompt": prompt, "response": response, "time": elapsed_time})

# --- Evaluate with judge model ---
evaluations = []

# Build comprehensive evaluation prompt with ALL prompts and responses
all_evaluations = ""
for prompt in prompts:
    answers = {}
    timings = {}
    for m in models:
        response_data = next(r for r in results[m] if r["prompt"] == prompt)
        answers[m] = response_data["response"]
        timings[m] = response_data["time"]
    all_evaluations += f"""
### PROMPT: {prompt}

Responses:
{json.dumps(answers, indent=2, ensure_ascii=False)}

Response Times:
{json.dumps({m: f"{t:.2f}s" for m, t in timings.items()}, indent=2)}

---

"""

comprehensive_evaluation_prompt = f"""
You are an evaluator. Compare the responses for the following prompts:

{all_evaluations}

For each model, assign a score from 1 to 5 considering clarity, correctness, and completeness.
Response times are shown for reference but focus your scoring on response quality.
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
        resp_data = next(r for r in results[model] if r["prompt"] == prompt)
        resp = resp_data["response"]
        elapsed = resp_data["time"]
        report.append(f"### Model: `{model}` ({elapsed:.2f}s)\n{resp}\n")

# Add timing summary with normalized scores
time_scores = calculate_time_scores(results)
report.append("## Timing Summary\n")
report.append("| Model | Total Time | Avg per Prompt | Time Score (1-5) |")
report.append("|-------|------------|----------------|------------------|")
for model in models:
    total_time = sum(r["time"] for r in results[model])
    avg_time = total_time / len(results[model]) if results[model] else 0
    time_score = time_scores.get(model, 0)
    report.append(f"| **{model}** | {total_time:.2f}s | {avg_time:.2f}s | {time_score:.2f} |")
report.append("")
report.append("*Time scores are normalized: fastest model = 5, slowest = 1, others interpolated.*\n")

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
