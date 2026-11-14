#!/usr/bin/env bash
# Збирання образів мікросервісів і публікація в локальний реєстр.
# Теги: v1, v2 - робочі версії; bad - навмисно несправна версія catalog
# (readiness-проба завжди повертає 503) для експерименту E2.
source "$(dirname "$0")/lib.sh"
need docker

for svc in catalog orders gateway; do
  for tag in v1 v2; do
    image="${REGISTRY_PUSH}/shop/${svc}:${tag}"
    log "Збирання ${image}"
    docker build -q --build-arg "APP_VERSION=${tag}" -t "${image}" "${ROOT}/services/${svc}"
    docker push -q "${image}"
  done
done

image="${REGISTRY_PUSH}/shop/catalog:bad"
log "Збирання ${image}"
docker build -q --build-arg APP_VERSION=bad --build-arg READY_FAIL=true -t "${image}" "${ROOT}/services/catalog"
docker push -q "${image}"

curl -s "http://${REGISTRY_PUSH}/v2/_catalog"
echo
