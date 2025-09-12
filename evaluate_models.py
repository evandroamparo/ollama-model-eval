import subprocess
import json
from pathlib import Path
from statistics import mean

# --- Função para rodar modelo via Ollama ---
def run_ollama(model: str, prompt: str) -> str:
    result = subprocess.run(
        ["ollama", "run", model, prompt],
        capture_output=True,
        text=True
    )
    return result.stdout.strip()

# --- Carregar arquivos ---
prompts = Path("prompts.txt").read_text(encoding="utf-8").splitlines()
models = Path("models.txt").read_text(encoding="utf-8").splitlines()
judge_model = Path("judge.txt").read_text(encoding="utf-8").strip()

results = {model: [] for model in models}
scores = {model: [] for model in models}

# --- Executar prompts em todos os modelos ---
for model in models:
    for prompt in prompts:
        print(f"▶️ Rodando prompt no modelo {model}...")
        response = run_ollama(model, prompt)
        results[model].append({"prompt": prompt, "response": response})

# --- Avaliar com modelo juiz ---
evaluations = []
for prompt in prompts:
    answers = {
        m: next(r["response"] for r in results[m] if r["prompt"] == prompt)
        for m in models
    }
    evaluation_prompt = f"""
Você é um avaliador. Compare as respostas para o seguinte prompt:

PROMPT: {prompt}

Respostas:
{json.dumps(answers, indent=2, ensure_ascii=False)}

Para cada modelo, atribua uma nota de 1 a 5 considerando clareza, correção e completude.
No final, indique qual modelo respondeu melhor.
Formato esperado (JSON):
{{
  "scores": {{"modelo1": int, "modelo2": int, ...}},
  "melhor": "nome do modelo"
}}
"""
    print(f"⚖️ Avaliando respostas do prompt com {judge_model}...")
    judge_response = run_ollama(judge_model, evaluation_prompt)

    try:
        parsed = json.loads(judge_response)
        for model, score in parsed.get("scores", {}).items():
            if model in scores:
                scores[model].append(score)
    except:
        parsed = {"raw": judge_response}

    evaluations.append({"prompt": prompt, "evaluation": parsed})

# --- Calcular ranking ---
averages = {m: mean(vals) if vals else 0 for m, vals in scores.items()}
ranking = sorted(averages.items(), key=lambda x: x[1], reverse=True)

# --- Gerar relatório Markdown ---
report = ["# Relatório de Avaliação de Modelos\n"]

for prompt in prompts:
    report.append(f"## Prompt\n```\n{prompt}\n```")
    for model in models:
        resp = next(r["response"] for r in results[model] if r["prompt"] == prompt)
        report.append(f"### Modelo: `{model}`\n{resp}\n")
    ev = next(e for e in evaluations if e["prompt"] == prompt)["evaluation"]
    report.append("### Avaliação\n")
    report.append("```json\n" + json.dumps(ev, indent=2, ensure_ascii=False) + "\n```")

# --- Ranking final ---
report.append("# Ranking Final\n")
for i, (model, avg) in enumerate(ranking, 1):
    notas = ", ".join(str(s) for s in scores[model]) if scores[model] else "sem notas"
    report.append(f"{i}. **{model}** — Média: {avg:.2f} | Notas: [{notas}]")

Path("relatorio.md").write_text("\n\n".join(report), encoding="utf-8")

print("✅ Relatório gerado em relatorio.md")
