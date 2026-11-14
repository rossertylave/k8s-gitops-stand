#!/usr/bin/env bash
# Встановлення Argo CD з офіційного маніфесту зафіксованої версії.
source "$(dirname "$0")/lib.sh"
need kubectl

start=$(now_ms)
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd --server-side --force-conflicts \
  -f "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"
kubectl -n argocd wait --for=condition=Available deployment --all --timeout=600s
kubectl -n argocd rollout status statefulset/argocd-application-controller --timeout=600s
end=$(now_ms)

echo "argocd_install_ms,$(( end - start ))" >> "${RESULTS}/bootstrap_times.csv"
log "Argo CD встановлено. Пароль користувача admin:"
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
echo
log "Інтерфейс: kubectl -n argocd port-forward svc/argocd-server 8443:443  ->  https://localhost:8443"
