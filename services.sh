#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$DIR/logs"

# Locate vllm: prefer local .venv, fall back to yp-agent .venv, then PATH
if   [ -x "$DIR/.venv/bin/vllm" ];                            then VLLM="$DIR/.venv/bin/vllm"
elif [ -x "/home/jason_yp_wang/yp-agent/.venv/bin/vllm" ];   then VLLM="/home/jason_yp_wang/yp-agent/.venv/bin/vllm"
elif command -v vllm >/dev/null 2>&1;                              then VLLM="$(command -v vllm)"
else echo "ERROR: vllm not found. Run 'uv sync --extra gpu' or install vllm."; exit 1
fi


# ── Config ──
LLM_MODEL="${LLM_MODEL:-cyankiwi/Qwen3.5-9B-AWQ-4bit}"   LLM_PORT="${LLM_PORT:-8000}"   LLM_GPU="${LLM_GPU_UTIL:-0.4}"
ASR_MODEL="${ASR_MODEL:-Qwen/Qwen3-ASR-1.7B}"             ASR_PORT="${ASR_PORT:-8006}"   ASR_GPU="${ASR_GPU_UTIL:-0.15}"

# ── Colors ──
G='\033[32m' R='\033[31m' Y='\033[33m' D='\033[2m' B='\033[1m' N='\033[0m'

alive() { tmux has-session -t "$1" 2>/dev/null; }

enable_logging() {
    local session=$1
    local logfile="$LOG_DIR/${session}.log"
    echo -e "\n=== $(date '+%Y-%m-%d %H:%M:%S') === session start ===" >> "$logfile"
    tmux pipe-pane -t "$session" "sed 's/\x1b\[[0-9;]*[a-zA-Z]//g; s/\x1b([A-Z]//g; s/\r//g' >> '$logfile'"
}

wait_healthy() {
    local url=$1 name=$2 s=0
    printf "  ${D}waiting for ${name}${N}"
    while ! curl -sf "$url" >/dev/null 2>&1; do
        printf "${D}.${N}"; sleep 5; s=$((s + 5))
    done
    echo -e " ${G}ready${N} ${D}(${s}s)${N}"
}

cmd_start() {
    mkdir -p "$LOG_DIR"
    echo -e "${B}Starting services${N}"

    # LLM vLLM (for extraction: transcript polish + meeting note)
    echo -e "\n  ${B}LLM${N} ${D}:${LLM_PORT}${N}"
    if alive llm-vllm; then
        echo -e "  ${G}●${N} already running"
    else
        echo -e "  ${D}${LLM_MODEL}${N}"
        tmux new-session -d -s llm-vllm \
            "$VLLM serve $LLM_MODEL --port $LLM_PORT --gpu-memory-utilization $LLM_GPU --tensor-parallel-size 1 --max-model-len 32768"
        enable_logging "llm-vllm"
        echo -e "  ${G}●${N} started  ${D}→ logs/llm-vllm.log${N}"
    fi

    wait_healthy "http://localhost:$LLM_PORT/health" "LLM"

    # ASR vLLM
    echo -e "\n  ${B}ASR${N} ${D}:${ASR_PORT}${N}"
    if alive asr-vllm; then
        echo -e "  ${G}●${N} already running"
    else
        echo -e "  ${D}${ASR_MODEL}${N}"
        tmux new-session -d -s asr-vllm \
            "$VLLM serve $ASR_MODEL --port $ASR_PORT --gpu-memory-utilization $ASR_GPU --max-model-len 4096"
        enable_logging "asr-vllm"
        echo -e "  ${G}●${N} started  ${D}→ logs/asr-vllm.log${N}"
    fi

    wait_healthy "http://localhost:$ASR_PORT/health" "ASR"
    echo
}

cmd_stop() {
    echo -e "${B}Stopping services${N}"
    for s in llm-vllm asr-vllm; do
        if alive "$s"; then
            tmux kill-session -t "$s"
            echo -e "  ${R}●${N} $s stopped"
        fi
    done
    echo -e "  done"
}

cmd_status() {
    echo -e "\n${B}Services${N}"
    for entry in "LLM:$LLM_PORT:llm-vllm" "ASR:$ASR_PORT:asr-vllm"; do
        IFS=: read -r name port session <<< "$entry"
        if alive "$session"; then
            printf "  ${G}●${N} %-12s ${D}:%-5s  tmux: %s${N}\n" "$name" "$port" "$session"
        else
            printf "  ${R}○${N} %-12s ${D}:%-5s${N}\n" "$name" "$port"
        fi
    done
    echo
}

cmd_logs() {
    local s="${1:?Usage: $0 logs <llm-vllm|asr-vllm>}"
    alive "$s" && tmux attach -t "$s" || { echo "Session '$s' not found"; exit 1; }
}

case "${1:-start}" in
    start)  cmd_start ;;
    stop)   cmd_stop ;;
    status) cmd_status ;;
    logs)   cmd_logs "${2:-}" ;;
    *)      echo "Usage: $0 {start|stop|status|logs <session>}"; exit 1 ;;
esac
