# Короткі команди для роботи зі стендом. Повний порядок дій - у README.md.
REPO_URL ?=
N ?= 10

.PHONY: check cluster images argocd gitops manual up test render e0 e1 e2 e3 e4 e5 analyze destroy

check:      ; bootstrap/00-check.sh
cluster:    ; bootstrap/01-cluster.sh
images:     ; bootstrap/02-images.sh
argocd:     ; bootstrap/03-argocd.sh
gitops:     ; bootstrap/04-gitops.sh $(REPO_URL)
manual:     ; bootstrap/05-manual-env.sh
up: check cluster images argocd gitops manual

test:
	for s in catalog orders gateway; do (cd services/$$s && python3 -m pytest -q) || exit 1; done
render:
	for e in dev prod manual; do kubectl kustomize gitops/apps/shop/overlays/$$e > /dev/null && echo "$$e ok"; done

e0: ; experiments/e0_calibrate.sh dev
e1:
	experiments/e1_deploy_time.sh manual $(N)
	experiments/e1_deploy_time.sh gitops-refresh $(N)
	experiments/e1_deploy_time.sh gitops-poll $(N)
e2: ; experiments/e2_bad_release.sh 5
e3: ; experiments/e3_selfheal.sh $(N)
e4:
	experiments/e4_hpa.sh dev
	sleep 180
	experiments/e4_hpa.sh manual
e5: ; experiments/e5_pod_failure.sh $(N)
analyze: ; python3 experiments/analyze.py

destroy: ; bootstrap/99-destroy.sh
