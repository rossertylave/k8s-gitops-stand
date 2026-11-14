#!/usr/bin/env bash
# Підключення репозиторію до Argo CD: застосування кореневого застосунку (app-of-apps).
# Використання: bootstrap/04-gitops.sh https://github.com/<користувач>/k8s-gitops-stand.git
source "$(dirname "$0")/lib.sh"
need kubectl git

repo_url="${1:?Вкажіть URL публічного Git-репозиторію}"

# Підстановка URL репозиторію в маніфести Argo CD
grep -rl "https://github.com/CHANGE_ME/k8s-gitops-stand.git" "${ROOT}/gitops/root" "${ROOT}/bootstrap/root-app.yaml" 2>/dev/null \
  | while read -r file; do
      sed -i.bak "s|https://github.com/CHANGE_ME/k8s-gitops-stand.git|${repo_url}|g" "${file}"
      rm -f "${file}.bak"
    done

if ! git -C "${ROOT}" diff --quiet; then
  git -C "${ROOT}" add gitops bootstrap/root-app.yaml
  git -C "${ROOT}" commit -q -m "bootstrap: set repository URL"
  git -C "${ROOT}" push -q origin main
fi

start=$(now_ms)
kubectl apply -f "${ROOT}/bootstrap/root-app.yaml"

log "Очікування синхронізації застосунків (до 15 хв: завантажуються образи моніторингу)"
deadline=$(( $(date +%s) + 900 ))
while true; do
  status="$(kubectl -n argocd get applications \
    -o jsonpath='{range .items[*]}{.metadata.name}={.status.sync.status}/{.status.health.status}{"\n"}{end}' 2>/dev/null || true)"
  total="$(printf '%s\n' "${status}" | grep -c '=' || true)"
  ok="$(printf '%s\n' "${status}" | grep -c '=Synced/Healthy' || true)"
  if (( total >= 4 && ok == total )); then break; fi
  if (( $(date +%s) > deadline )); then
    log "Тайм-аут. Поточний стан:"; printf '%s\n' "${status}"; exit 1
  fi
  sleep 5
done
end=$(now_ms)

echo "gitops_bootstrap_ms,$(( end - start ))" >> "${RESULTS}/bootstrap_times.csv"
kubectl -n argocd get applications
shop_curl dev /api/versions; echo
