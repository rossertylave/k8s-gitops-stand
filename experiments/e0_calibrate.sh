#!/usr/bin/env bash
# E0. Калібрування моделі: середній час обслуговування запиту S при малому
# навантаженні (черги практично немає) і споживання CPU подами catalog.
# Результат: results/e0_calibration.json (k6) та results/e0_top.txt.
source "$(dirname "$0")/../bootstrap/lib.sh"
need k6 kubectl

env_name="${1:-dev}"
RATE="${RATE:-2}" DURATION="${DURATION:-90s}" WORK="${WORK:-1}" \
HOST_HEADER="shop-${env_name}.localhost" BASE_URL="${BASE_URL}" \
  k6 run --quiet --summary-export "${RESULTS}/e0_calibration.json" "${ROOT}/experiments/k6/steady.js"

kubectl -n "shop-${env_name}" top pods | tee "${RESULTS}/e0_top.txt"
python3 - "${RESULTS}/e0_calibration.json" <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))["metrics"]["http_req_duration"]
print(f"Середній час відповіді S = {m['avg']:.1f} мс; p95 = {m['p(95)']:.1f} мс")
print(f"Оцінка інтенсивності обслуговування однією реплікою: mu = {1000 / m['avg']:.1f} запитів/с")
PY
