#!/usr/bin/env bash
# Спільні змінні та функції скриптів стенда.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT
export CLUSTER_NAME="stand"
export REGISTRY_NAME="stand-registry.localhost"          # k3d додасть префікс k3d-
export REGISTRY_PORT="5001"
export REGISTRY_PUSH="localhost:${REGISTRY_PORT}"         # адреса з хоста
export REGISTRY_PULL="k3d-${REGISTRY_NAME}:${REGISTRY_PORT}"  # адреса з кластера
export ARGOCD_VERSION="v3.6.1"
export RESULTS="${ROOT}/experiments/results"
export BASE_URL="${BASE_URL:-http://localhost:8080}"
mkdir -p "${RESULTS}"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

# Час у мілісекундах (python3 замість date +%N заради сумісності з macOS).
now_ms() { python3 -c 'import time; print(int(time.time() * 1000))'; }

need() {
  for bin in "$@"; do
    command -v "${bin}" >/dev/null 2>&1 || { log "Не знайдено: ${bin}"; exit 1; }
  done
}

# Поточний образ першого контейнера Deployment: deploy_image <ns> <name>
deploy_image() {
  kubectl -n "$1" get deployment "$2" -o jsonpath='{.spec.template.spec.containers[0].image}'
}

# Очікування, доки образ Deployment закінчуватиметься на :<tag>.
# wait_image_tag <ns> <name> <tag> <timeout_s>
wait_image_tag() {
  local deadline=$(( $(date +%s) + $4 ))
  until [[ "$(deploy_image "$1" "$2")" == *":$3" ]]; do
    if (( $(date +%s) > deadline )); then
      log "Тайм-аут: $1/$2 не отримав тег $3 за $4 с"
      return 1
    fi
    sleep 0.5
  done
}

# Зміна тега образу сервісу в overlay: set_tag <env> <service> <tag>
set_tag() {
  local file="${ROOT}/gitops/apps/shop/overlays/$1/kustomization.yaml"
  sed -i.bak "s|newTag: .* # $2-tag|newTag: $3 # $2-tag|" "${file}"
  rm -f "${file}.bak"
}

# Фіксація і надсилання змін каталогу gitops у віддалений репозиторій.
git_push() {
  git -C "${ROOT}" add gitops
  git -C "${ROOT}" commit -q -m "$1"
  git -C "${ROOT}" push -q origin main
}

# Примусове оновлення стану застосунку Argo CD (еквівалент вебхука від Git-сервера).
argocd_refresh() {
  kubectl -n argocd annotate application "$1" argocd.argoproj.io/refresh=normal --overwrite >/dev/null
}

# HTTP-запит до застосунку через Ingress: shop_curl <env> <path>
shop_curl() {
  curl -s --max-time 5 -H "Host: shop-$1.localhost" "${BASE_URL}$2"
}
