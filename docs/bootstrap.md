# Bootstrap

## Local

```bash
cd /Users/chichau/current_projects/f713-control-plane
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Remote `f713`

```bash
mkdir -p /hdd/chichau/current_projects
cd /hdd/chichau/current_projects
git clone <github-remote> f713-control-plane
cd f713-control-plane
/home/chichau/miniconda3/bin/conda create -n f713ctl python=3.11 nodejs git openssl -y
source /home/chichau/miniconda3/etc/profile.d/conda.sh
conda activate f713ctl
npm install -g @openai/codex
pip install -e .
mkdir -p ~/.config/f713-control-plane ~/.codex
```

Create `~/.config/f713-control-plane/.env` and add:

```bash
FEISHU_APP_ID=...
FEISHU_APP_SECRET=...
FEISHU_OPEN_ID_OWNER=...
F713_CONTROL_FEISHU_ENABLED=1
F713_CONTROL_GIT_PUSH=1
F713_CONTROL_GIT_BRANCH=main
F713_CONTROL_GIT_REMOTE=origin
GITHUB_APP_ID=3037528
GITHUB_APP_INSTALLATION_ID=114826612
GITHUB_APP_OWNER=chichaumiao-openclaw
GITHUB_APP_PEM_PATH=/home/chichau/.config/f713-control-plane/chichaumiao-eng.private-key.pem
F713_CONTROL_CODEX_BIN=/home/chichau/miniconda3/envs/f713ctl/bin/codex
F713_CONTROL_CODEX_PROFILE=agnes
F713_CONTROL_CODEX_BASE_URL=https://apihub.agnes-ai.com/v1
F713_CONTROL_CODEX_MODEL=agnes-2.0-flash
```

Copy the GitHub App PEM to:

```bash
/home/chichau/.config/f713-control-plane/chichaumiao-eng.private-key.pem
```

Create `~/.codex/config.toml` with a minimal Agnes profile for cluster execution.
