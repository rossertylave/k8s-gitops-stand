#!/usr/bin/env bash
# E3. Самовідновлення конфігурації (усунення дрейфу) засобами Argo CD selfHeal.
# Два види ручного втручання в shop-dev:
#   env    - додавання змінної середовища DRIFT у Deployment orders;
#   delete - видалення Service catalog.
# Вимірюється час від втручання до повернення стану, описаного в Git.
# Використання: e3_selfheal.sh [кількість_запусків]
# Результат: results/e3_selfheal.csv  (drift,run,t_heal_ms)
source "$(dirname "$0")/../bootstrap/lib.sh"
need kubectl

runs="${1:-10}"
csv="${RESULTS}/e3_selfheal.csv"
[[ -f "${csv}" ]] || echo "drift,run,t_heal_ms" > "${csv}"

env_names() {
  kubectl -n shop-dev get deployment orders -o jsonpath='{.spec.template.spec.containers[0].env[*].name}'
}

for run in $(seq 1 "${runs}"); do
  # 1) дрейф конфігурації Deployment
  t0=$(now_ms)
  kubectl -n shop-dev set env deployment/orders "DRIFT=run${run}" >/dev/null
  deadline=$(( $(date +%s) + 300 ))
  while env_names | grep -qw DRIFT; do
    (( $(date +%s) > deadline )) && { log "Тайм-аут усунення дрейфу env"; exit 1; }
    sleep 0.5
  done
  t1=$(now_ms)
  echo "env,${run},$(( t1 - t0 ))" >> "${csv}"
  log "env: дрейф усунено за $(( t1 - t0 )) мс"
  kubectl -n shop-dev rollout status deployment/orders --timeout=300s >/dev/null
  sleep 10

  # 2) видалення ресурсу
  t0=$(now_ms)
  kubectl -n shop-dev delete service catalog --wait=true >/dev/null
  deadline=$(( $(date +%s) + 300 ))
  until kubectl -n shop-dev get service catalog >/dev/null 2>&1; do
    (( $(date +%s) > deadline )) && { log "Тайм-аут відновлення Service"; exit 1; }
    sleep 0.5
  done
  t1=$(now_ms)
  echo "delete,${run},$(( t1 - t0 ))" >> "${csv}"
  log "delete: Service відновлено за $(( t1 - t0 )) мс"
  sleep 10
done
