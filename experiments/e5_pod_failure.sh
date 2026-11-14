#!/usr/bin/env bash
# E5. Відмовостійкість: примусове видалення пода catalog під сталим навантаженням.
# Вимірюється час відновлення заданої кількості готових реплік і частка помилок.
# Використання: e5_pod_failure.sh [кількість_запусків]
# Результат: results/e5_pod_failure.csv (run,t_recover_ms,requests,failed)
# Додатково (необов'язково): NODE_FAILURE=1 e5_pod_failure.sh 1 - зупинка робочого
# вузла k3d-stand-agent-1 на 7 хв (перевірка поведінки при відмові вузла).
source "$(dirname "$0")/../bootstrap/lib.sh"
need kubectl k6

runs="${1:-10}"
csv="${RESULTS}/e5_pod_failure.csv"
[[ -f "${csv}" ]] || echo "run,t_recover_ms,requests,failed" > "${csv}"

ready_replicas() {
  kubectl -n shop-dev get deployment catalog -o jsonpath='{.status.readyReplicas}'
}

k6_start() { # k6_start <duration> <summary>; PID фонового процесу - у змінній K6_PID
  RATE="${RATE:-5}" DURATION="$1" WORK=1 HOST_HEADER="shop-dev.localhost" \
    k6 run --quiet --summary-export "$2" "${ROOT}/experiments/k6/steady.js" >/dev/null 2>&1 &
  K6_PID=$!
}

k6_result() { # друкує "<requests> <failed>"
  python3 - "$1" <<'PY'
import json, sys
c = json.load(open(sys.argv[1]))["metrics"]["checks"]
print(c["passes"] + c["fails"], c["fails"])
PY
}

if [[ "${NODE_FAILURE:-0}" == "1" ]]; then
  need docker
  summary="${RESULTS}/e5_node_k6.json"
  timeline="${RESULTS}/e5_node_timeline.csv"
  echo "t_s,ready,nodes_ready" > "${timeline}"
  k6_start 480s "${summary}"
  sleep 30
  log "Зупинка вузла k3d-${CLUSTER_NAME}-agent-1"
  docker stop "k3d-${CLUSTER_NAME}-agent-1" >/dev/null
  start=$(date +%s)
  while (( $(date +%s) - start < 420 )); do
    nodes="$(kubectl get nodes --no-headers 2>/dev/null | grep -cw Ready || true)"
    echo "$(( $(date +%s) - start )),$(ready_replicas),${nodes}" >> "${timeline}"
    sleep 5
  done
  docker start "k3d-${CLUSTER_NAME}-agent-1" >/dev/null
  wait "${K6_PID}" || true
  log "Відмова вузла: запитів/помилок: $(k6_result "${summary}")"
  exit 0
fi

for run in $(seq 1 "${runs}"); do
  desired="$(ready_replicas)"
  summary="${RESULTS}/e5_k6_run${run}.json"
  k6_start 90s "${summary}"
  sleep 20

  victim="$(kubectl -n shop-dev get pods -l app.kubernetes.io/name=catalog -o jsonpath='{.items[0].metadata.name}')"
  t0=$(now_ms)
  kubectl -n shop-dev delete pod "${victim}" --grace-period=0 --force >/dev/null 2>&1
  # спершу дочекатись, доки кількість готових реплік зменшиться, потім - відновиться
  for _ in $(seq 1 20); do [[ "$(ready_replicas)" != "${desired}" ]] && break; sleep 0.25; done
  until [[ "$(ready_replicas)" == "${desired}" ]]; do sleep 0.25; done
  t1=$(now_ms)

  wait "${K6_PID}" || true
  read -r requests failed < <(k6_result "${summary}")
  echo "${run},$(( t1 - t0 )),${requests},${failed}" >> "${csv}"
  log "Запуск ${run}: відновлення $(( t1 - t0 )) мс, помилок ${failed}/${requests}"
  sleep 15
done
