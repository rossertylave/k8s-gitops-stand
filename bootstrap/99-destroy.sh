#!/usr/bin/env bash
# Повне видалення стенда.
source "$(dirname "$0")/lib.sh"
k3d cluster delete "${CLUSTER_NAME}" || true
k3d registry delete "k3d-${REGISTRY_NAME}" || true
