# k8s-gitops-stand

Стенд до магістерської кваліфікаційної роботи «Проєктування Kubernetes-інфраструктури
для автоматизованого розгортання мікросервісних застосунків».

Склад: кластер Kubernetes (k3s у k3d: 1 control plane + 2 робочі вузли), локальний реєстр
образів, Argo CD (GitOps, патерн app-of-apps), моніторинг (kube-prometheus-stack),
демонстраційний мікросервісний застосунок `shop` (gateway, catalog, orders), CI-конвеєр
GitHub Actions та скрипти експериментів E0–E5.

```
cluster/        декларативний опис кластера k3d
bootstrap/      скрипти розгортання стенда (00..05, 99-destroy)
gitops/root/    застосунки Argo CD (AppProject, monitoring, shop-dev, shop-prod)
gitops/apps/    Kustomize: base + overlays dev / prod / manual
services/       вихідний код мікросервісів, Dockerfile, модульні тести
experiments/    скрипти вимірювань, сценарії k6, analyze.py, results/
models/         розрахункові моделі з розділу 2 (графіки і таблиці)
.github/        CI-конвеєр
```

## 1. Вимоги

- Linux або macOS (Windows - через WSL2), 4+ ядра CPU, 8+ ГБ RAM, ~10 ГБ диска.
- Docker, k3d, kubectl, git, python3, curl, k6; для `analyze.py` - `pip install matplotlib`.
- Публічний Git-репозиторій (GitHub/GitLab), з якого Argo CD читатиме маніфести.

## 2. Розгортання

```bash
# 1) створити порожній публічний репозиторій і надіслати в нього цей каталог
git init -b main && git add -A && git commit -m "initial"
git remote add origin https://github.com/<користувач>/k8s-gitops-stand.git
git push -u origin main

# 2) розгорнути стенд (10-20 хв, більшість часу - завантаження образів)
make up REPO_URL=https://github.com/<користувач>/k8s-gitops-stand.git
```

`make up` послідовно виконує: перевірку інструментів і запис версій
(`experiments/results/versions.txt`), створення реєстру і кластера, збирання образів
`v1`, `v2`, `bad`, встановлення Argo CD, застосування кореневого застосунку,
розгортання контрольного середовища `shop-manual`.

Перевірка:

```bash
kubectl get nodes
kubectl -n argocd get applications          # усі Synced / Healthy
curl -H "Host: shop-dev.localhost" http://localhost:8080/api/versions
curl -H "Host: shop-dev.localhost" -X POST http://localhost:8080/api/orders \
     -H "content-type: application/json" -d '{"item_id": 4, "qty": 3}'
```

Інтерфейси:

```bash
kubectl -n argocd port-forward svc/argocd-server 8443:443        # https://localhost:8443, admin / пароль з кроку argocd
kubectl -n monitoring get svc | grep grafana                     # уточнити ім'я сервісу Grafana
kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80 # http://localhost:3000, admin / stand-admin
```

## 3. Експерименти

Виконувати по одному, на незавантаженій машині. Робоче дерево Git має бути чистим.

| Команда | Що вимірюється | Орієнтовна тривалість |
|---|---|---|
| `make e0` | середній час обслуговування запиту (калібрування моделі) | 2 хв |
| `make e1 N=10` | час доставки зміни: kubectl / GitOps refresh / GitOps опитування | 45-60 хв |
| `make e2` | несправний реліз під навантаженням і відкат через `git revert` | 20 хв |
| `make e3 N=10` | усунення дрейфу конфігурації (selfHeal) | 10 хв |
| `make e4` | автомасштабування (HPA 2..6 проти фіксованих 2 реплік) | 35 хв |
| `make e5 N=10` | відновлення після відмови пода | 20 хв |
| `make analyze` | зведені таблиці `results/summary.md` і рисунки `results/fig_*.png` | - |

Перед `make e4` підберіть інтенсивність навантаження за результатом `make e0`:
`RATE_HIGH` має вимагати 4-5 реплік catalog (розрахунок - формула (2.12) роботи).
Приклад: `RATE_LOW=5 RATE_HIGH=30 make e4`.

Необов'язково: `NODE_FAILURE=1 experiments/e5_pod_failure.sh 1` - відмова робочого вузла.

## 4. Що зберегти для пояснювальної записки

- `experiments/results/versions.txt`, `summary.md`, `fig_e1_deploy_time.png`, `fig_e4_hpa.png`;
- знімки екрана: `kubectl get nodes -o wide`; дерево застосунків Argo CD; застосунок
  `shop-dev` в Argo CD (Synced/Healthy); стан OutOfSync/Degraded під час `make e2`;
  панель Grafana «Kubernetes / Compute Resources / Namespace (Pods)» для `shop-dev` під час
  `make e4`; `kubectl -n shop-dev get hpa` на плато навантаження; успішний запуск конвеєра
  GitHub Actions (час виконання кожного job).

## 5. Видалення

```bash
make destroy
```

## Відомі обмеження

- Стенд локальний: усі вузли - контейнери на одній машині, тому відмова фізичного
  сервера, мережеві затримки між вузлами та продуктивність сховища не моделюються.
- Сервіс orders зберігає стан у пам'яті; СКБД і постійні томи в стенд не включено.
- Пароль Grafana заданий відкрито в маніфесті - допустимо лише для локального стенда.
- CI-конвеєр публікує образи в GHCR; у локальних експериментах використовується
  локальний реєстр, а роль кроку «оновити тег у Git» виконують скрипти `experiments/`.
