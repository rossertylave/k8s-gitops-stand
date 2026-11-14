#!/usr/bin/env bash
# Контрольне середовище shop-manual: розгортається імперативно (kubectl apply -k),
# Argo CD ним не керує. Потрібне для порівняння в експериментах E1 та E4.
source "$(dirname "$0")/lib.sh"
need kubectl

kubectl create namespace shop-manual --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -k "${ROOT}/gitops/apps/shop/overlays/manual"
for d in catalog orders gateway; do
  kubectl -n shop-manual rollout status "deployment/${d}" --timeout=300s
done
shop_curl manual /api/versions; echo
