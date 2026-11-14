#!/usr/bin/env bash
# E1. Час доставки зміни (нова версія сервісу catalog) у кластер для трьох способів:
#   manual          - імперативно: kubectl set image у просторі shop-manual;
#   gitops-poll     - commit + push, Argo CD виявляє зміну періодичним опитуванням;
#   gitops-refresh  - commit + push + негайний refresh (еквівалент вебхука).
# Використання: e1_deploy_time.sh <mode> [кількість_запусків]
# Результат: results/e1_deploy_time.csv
#   mode,run,tag,t_git_ms,t_detect_ms,t_rollout_ms,t_total_ms
source "$(dirname "$0")/../bootstrap/lib.sh"
need kubectl git

mode="${1:?mode: manual | gitops-poll | gitops-refresh}"
runs="${2:-10}"
csv="${RESULTS}/e1_deploy_time.csv"
[[ -f "${csv}" ]] || echo "mode,run,tag,t_git_ms,t_detect_ms,t_rollout_ms,t_total_ms" > "${csv}"

case "${mode}" in
  manual) ns="shop-manual" ;;
  gitops-poll | gitops-refresh) ns="shop-dev" ;;
  *) log "Невідомий режим: ${mode}"; exit 1 ;;
esac

for run in $(seq 1 "${runs}"); do
  if [[ "$(deploy_image "${ns}" catalog)" == *":v1" ]]; then tag="v2"; else tag="v1"; fi
  log "[${mode}] запуск ${run}/${runs}: catalog -> ${tag}"

  t0=$(now_ms)
  if [[ "${mode}" == "manual" ]]; then
    kubectl -n "${ns}" set image deployment/catalog "catalog=${REGISTRY_PULL}/shop/catalog:${tag}" >/dev/null
    t_git=${t0}
  else
    set_tag dev catalog "${tag}"
    git_push "deploy(dev): catalog ${tag} (E1 ${mode} run ${run})"
    t_git=$(now_ms)
    if [[ "${mode}" == "gitops-refresh" ]]; then argocd_refresh shop-dev; fi
  fi

  wait_image_tag "${ns}" catalog "${tag}" 600
  t1=$(now_ms)
  kubectl -n "${ns}" rollout status deployment/catalog --timeout=600s >/dev/null
  t2=$(now_ms)

  echo "${mode},${run},${tag},$(( t_git - t0 )),$(( t1 - t0 )),$(( t2 - t1 )),$(( t2 - t0 ))" >> "${csv}"
  log "  виявлення $(( t1 - t0 )) мс, оновлення подів $(( t2 - t1 )) мс, разом $(( t2 - t0 )) мс"
  sleep 20   # пауза між запусками, щоб завершились попередні поди
done
