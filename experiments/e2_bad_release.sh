#!/usr/bin/env bash
# E2. Несправний реліз і відкат через Git.
# Під сталим навантаженням у shop-dev розгортається catalog:bad (readiness = 503).
# Оцінюється: чи зберігається обслуговування (стратегія maxUnavailable=0),
# і час відновлення після git revert.
# Використання: e2_bad_release.sh [кількість_запусків]
# Результат: results/e2_bad_release.csv
#   run,ready_old_during_bad,rollout_blocked,t_revert_detect_ms,t_recover_ms,requests,failed
source "$(dirname "$0")/../bootstrap/lib.sh"
need kubectl git k6

runs="${1:-5}"
hold_s="${HOLD_S:-60}"
csv="${RESULTS}/e2_bad_release.csv"
[[ -f "${csv}" ]] || echo "run,ready_old_during_bad,rollout_blocked,t_revert_detect_ms,t_recover_ms,requests,failed" > "${csv}"

for run in $(seq 1 "${runs}"); do
  good="$(deploy_image shop-dev catalog)"; good="${good##*:}"
  log "Запуск ${run}/${runs}: робоча версія ${good}"

  summary="${RESULTS}/e2_k6_run${run}.json"
  RATE="${RATE:-5}" DURATION="$(( hold_s + 120 ))s" WORK=1 HOST_HEADER="shop-dev.localhost" \
    k6 run --quiet --summary-export "${summary}" "${ROOT}/experiments/k6/steady.js" >/dev/null 2>&1 &
  k6_pid=$!
  sleep 15

  set_tag dev catalog bad
  git_push "deploy(dev): catalog bad (E2 run ${run})"
  argocd_refresh shop-dev
  wait_image_tag shop-dev catalog bad 300
  sleep "${hold_s}"

  # Стан під час несправного релізу
  ready_old="$(kubectl -n shop-dev get pods -l app.kubernetes.io/name=catalog \
    -o jsonpath='{range .items[*]}{.spec.containers[0].image}={.status.containerStatuses[0].ready}{"\n"}{end}' \
    | grep -v ':bad=' | grep -c '=true' || true)"
  if kubectl -n shop-dev rollout status deployment/catalog --timeout=5s >/dev/null 2>&1; then blocked="no"; else blocked="yes"; fi

  # Відкат: повернення попереднього коміту в Git
  t0=$(now_ms)
  git -C "${ROOT}" revert --no-edit HEAD >/dev/null
  git -C "${ROOT}" push -q origin main
  argocd_refresh shop-dev
  wait_image_tag shop-dev catalog "${good}" 300
  t1=$(now_ms)
  kubectl -n shop-dev rollout status deployment/catalog --timeout=300s >/dev/null
  t2=$(now_ms)

  wait "${k6_pid}" || true
  read -r requests failed < <(python3 - "${summary}" <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))["metrics"]
checks = m["checks"]
print(checks["passes"] + checks["fails"], checks["fails"])
PY
  )
  echo "${run},${ready_old},${blocked},$(( t1 - t0 )),$(( t2 - t0 )),${requests},${failed}" >> "${csv}"
  log "  робочих старих подів: ${ready_old}, оновлення заблоковано: ${blocked}, відновлення $(( t2 - t0 )) мс, помилок ${failed}/${requests}"
  sleep 20
done
