import subprocess
from pathlib import Path

def run_cmd(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout.strip())
    else:
        print(result.stderr.strip())

# Carregar modelos
models = Path("models.txt").read_text(encoding="utf-8").splitlines()
judge_model = Path("judge.txt").read_text(encoding="utf-8").strip()

print("📥 Baixando modelos...")

for model in models + [judge_model]:
    if model.strip():
        print(f"➡️  Pull do modelo: {model}")
        run_cmd(["ollama", "pull", model])

print("✅ Todos os modelos foram baixados.")
