#!/usr/bin/env bash
# ----------------------------------------------------------------------
# One‑click backend installer for aarch64 Ubuntu with Nvidia GPU
# ----------------------------------------------------------------------
set -e

# 1. System updates & prerequisites
echo "[*] Updating system …"
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y python3 python3-pip python3-venv git build-essential curl

# 2. Install NVIDIA drivers & CUDA (if not already present)
if ! nvidia-smi >/dev/null 2>&1; then
  echo "[*] Installing NVIDIA driver & CUDA toolkit …"
  sudo apt-get install -y nvidia-driver-560 cuda-toolkit-12-1
fi

# 3. Install Ollama (aarch64) – official script
echo "[*] Installing Ollama …"
curl -fsSL https://ollama.com/install.sh | sh

# 4. Pull Llama 3.1 8b‑instruct model
echo "[*] Pulling Llama 3.1 8b instructional model …"
ollama pull llama3.1:8b-instruct

# 5. Set up Python virtual environment
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate

# 6. Install Python deps
pip install -r requirements.txt

# 7. Start the FastAPI server (background with systemd)
cat <<EOF | sudo tee /etc/systemd/system/feelgood-backend.service > /dev/null
[Unit]
Description=Feel‑Good News Backend (FastAPI + Ollama)
After=network.target ollama.service
[Service]
User=$USER
WorkingDirectory=$(pwd)
Environment=OLLAMA_HOST=http://localhost:11434
ExecStart=$(pwd)/.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=on-failure
[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now feelgood-backend.service

echo "[✓] Installation complete!"
echo "Backend running on: http://$(hostname -I | awk '{print $1}'):8000"
echo "Configure your extension (chrome://extensions) → Options → set the IP above."