#!/usr/bin/env bash
# Перевірка наявності інструментів і фіксація їхніх версій (для таблиці в роботі).
source "$(dirname "$0")/lib.sh"
need docker k3d kubectl git python3 curl k6

out="${RESULTS}/versions.txt"
{
  echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "os: $(uname -srm)"
  echo "cpu_cores: $(python3 -c 'import os; print(os.cpu_count())')"
  echo "docker: $(docker version --format '{{.Server.Version}}')"
  echo "k3d: $(k3d version | tr '\n' ' ')"
  echo "kubectl: $(kubectl version --client -o json | python3 -c 'import json,sys; print(json.load(sys.stdin)["clientVersion"]["gitVersion"])')"
  echo "k6: $(k6 version)"
  echo "git: $(git --version)"
  echo "python: $(python3 --version)"
  echo "argocd (install manifest): ${ARGOCD_VERSION}"
} | tee "${out}"
log "Версії записано у ${out}"
