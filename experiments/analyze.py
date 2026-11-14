#!/usr/bin/env python3
"""Оброблення результатів експериментів E0-E5.

Читає CSV/JSON з experiments/results, друкує зведені таблиці (Markdown) у
results/summary.md і будує рисунки results/fig_*.png для розділу 4 роботи.

Запуск:  python3 experiments/analyze.py
Потрібно: matplotlib (pip install matplotlib)
"""
import csv
import gzip
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RES = Path(__file__).resolve().parent / "results"
OUT = []

# Двобічні критичні значення t-розподілу Стьюдента для довірчої ймовірності 0,95
T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
       9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
       16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 25: 2.060, 30: 2.042}

plt.rcParams.update({"font.family": "DejaVu Serif", "font.size": 11, "figure.dpi": 150})


def t95(df: int) -> float:
    if df in T95:
        return T95[df]
    if df > 30:
        return 1.96
    return T95[max(k for k in T95 if k <= df)]


def stats(values):
    """Повертає (n, середнє, СКВ, мін, макс, півширина 95 % довірчого інтервалу)."""
    n = len(values)
    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if n > 1 else 0.0
    half = t95(n - 1) * sd / math.sqrt(n) if n > 1 else float("nan")
    return n, mean, sd, min(values), max(values), half


def read_csv(name):
    path = RES / name
    if not path.exists():
        return None
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def emit(line=""):
    OUT.append(line)
    print(line)


def table(header, rows):
    emit("| " + " | ".join(header) + " |")
    emit("|" + "---|" * len(header))
    for row in rows:
        emit("| " + " | ".join(str(c) for c in row) + " |")
    emit()


def fmt(x, digits=2):
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{digits}f}"


def e0():
    path = RES / "e0_calibration.json"
    if not path.exists():
        return
    m = json.loads(path.read_text())["metrics"]["http_req_duration"]
    emit("## E0. Калібрування")
    table(["Показник", "Значення"],
          [["Середній час відповіді S, мс", fmt(m["avg"], 1)],
           ["p95, мс", fmt(m["p(95)"], 1)],
           ["Оцінка mu = 1/S, запитів/с на репліку", fmt(1000 / m["avg"], 1)]])


def e1():
    rows = read_csv("e1_deploy_time.csv")
    if not rows:
        return
    emit("## E1. Час доставки зміни, с")
    modes = ["manual", "gitops-poll", "gitops-refresh"]
    labels = {"manual": "Імперативно (kubectl)", "gitops-poll": "GitOps, опитування",
              "gitops-refresh": "GitOps, негайний refresh"}
    out, means = [], {}
    for mode in modes:
        sel = [r for r in rows if r["mode"] == mode]
        if not sel:
            continue
        for col, title in (("t_detect_ms", "виявлення"), ("t_rollout_ms", "оновлення подів"),
                           ("t_total_ms", "разом")):
            n, mean, sd, lo, hi, half = stats([int(r[col]) / 1000 for r in sel])
            out.append([labels[mode], title, n, fmt(mean), fmt(sd), fmt(lo), fmt(hi), "±" + fmt(half)])
            means[(mode, col)] = mean
    table(["Спосіб", "Складова", "n", "Середнє", "СКВ", "Мін", "Макс", "95 % ДІ"], out)

    present = [m for m in modes if (m, "t_total_ms") in means]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    detect = [means[(m, "t_detect_ms")] for m in present]
    rollout = [means[(m, "t_rollout_ms")] for m in present]
    ax.bar(range(len(present)), detect, color="#4c72b0", label="виявлення зміни")
    ax.bar(range(len(present)), rollout, bottom=detect, color="#dd8452", label="оновлення подів")
    ax.set_xticks(range(len(present)), [labels[m] for m in present])
    ax.set_ylabel("Час, с")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(RES / "fig_e1_deploy_time.png")
    plt.close(fig)


def e2():
    rows = read_csv("e2_bad_release.csv")
    if not rows:
        return
    emit("## E2. Несправний реліз і відкат через Git")
    n, mean, sd, lo, hi, half = stats([int(r["t_recover_ms"]) / 1000 for r in rows])
    requests = sum(int(r["requests"]) for r in rows)
    failed = sum(int(r["failed"]) for r in rows)
    blocked = sum(1 for r in rows if r["rollout_blocked"] == "yes")
    table(["Показник", "Значення"],
          [["Кількість запусків", n],
           ["Оновлення заблоковано readiness-пробою, запусків", f"{blocked} з {n}"],
           ["Мін. кількість робочих подів попередньої версії", min(int(r["ready_old_during_bad"]) for r in rows)],
           ["Час відновлення після git revert, с (середнє ± 95 % ДІ)", f"{fmt(mean)} ± {fmt(half)}"],
           ["Мін / макс, с", f"{fmt(lo)} / {fmt(hi)}"],
           ["Запитів усього / з помилкою", f"{requests} / {failed}"],
           ["Частка помилок, %", fmt(100 * failed / requests if requests else float('nan'), 3)]])


def e3():
    rows = read_csv("e3_selfheal.csv")
    if not rows:
        return
    emit("## E3. Усунення дрейфу конфігурації (selfHeal), с")
    out = []
    for drift, title in (("env", "Зміна Deployment (env)"), ("delete", "Видалення Service")):
        sel = [int(r["t_heal_ms"]) / 1000 for r in rows if r["drift"] == drift]
        if sel:
            n, mean, sd, lo, hi, half = stats(sel)
            out.append([title, n, fmt(mean), fmt(sd), fmt(lo), fmt(hi), "±" + fmt(half)])
    table(["Вид втручання", "n", "Середнє", "СКВ", "Мін", "Макс", "95 % ДІ"], out)


def k6_windows(path, window=10):
    """p95 часу відповіді та частка помилок у вікнах по window секунд."""
    durations, failed, start = defaultdict(list), defaultdict(list), None
    with gzip.open(path, "rt", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = row["metric_name"]
            if name not in ("http_req_duration", "http_req_failed"):
                continue
            ts = int(row["timestamp"])
            start = ts if start is None else min(start, ts)
            bucket = ts // window * window
            (durations if name == "http_req_duration" else failed)[bucket].append(float(row["metric_value"]))
    xs = sorted(durations)
    p95 = [sorted(durations[b])[max(0, math.ceil(0.95 * len(durations[b])) - 1)] for b in xs]
    err = [100 * statistics.fmean(failed[b]) if failed.get(b) else 0.0 for b in xs]
    rate = [len(durations[b]) / window for b in xs]
    return [b - xs[0] for b in xs], p95, err, rate


def e4():
    emit_header = True
    fig, axes = plt.subplots(3, 1, figsize=(7.5, 8), sharex=True)
    drawn = False
    out = []
    for env, title, color in (("dev", "HPA 2..6 реплік", "#4c72b0"), ("manual", "фіксовано 2 репліки", "#c44e52")):
        hpa = read_csv(f"e4_{env}_hpa.csv")
        k6_path = RES / f"e4_{env}_k6.csv.gz"
        summary_path = RES / f"e4_{env}_summary.json"
        if not hpa or not k6_path.exists() or not summary_path.exists():
            continue
        if emit_header:
            emit("## E4. Автомасштабування під змінним навантаженням")
            emit_header = False
        drawn = True
        hpa = [r for r in hpa if r["current"]]
        t = [int(r["t_s"]) for r in hpa]
        current = [int(r["current"]) for r in hpa]
        xs, p95, err, rate = k6_windows(k6_path)
        axes[0].plot(xs, rate, color="gray", lw=1) if env == "dev" else None
        axes[1].step(t, current, where="post", color=color, label=title)
        axes[2].plot(xs, p95, color=color, label=title)

        m = json.loads(summary_path.read_text())["metrics"]
        checks = m["checks"]
        total = checks["passes"] + checks["fails"]
        base = current[0]
        first_up = next((ti for ti, c in zip(t, current) if c > base), None)
        t_max = next((ti for ti, c in zip(t, current) if c == max(current)), None)
        out.append([title, total, fmt(100 * checks["fails"] / total, 3), fmt(m["http_req_duration"]["avg"], 1),
                    fmt(m["http_req_duration"]["p(95)"], 1), fmt(m["http_req_duration"]["p(99)"], 1),
                    max(current), first_up if first_up is not None else "-", t_max if t_max is not None else "-"])
    if not drawn:
        plt.close(fig)
        return
    table(["Конфігурація", "Запитів", "Помилок, %", "Сер. час, мс", "p95, мс", "p99, мс",
           "Макс. реплік", "Перше масштабування, с", "Досягнення максимуму, с"], out)
    axes[0].set_ylabel("Інтенсивність,\nзапитів/с")
    axes[1].set_ylabel("Кількість реплік\ncatalog")
    axes[2].set_ylabel("p95 часу\nвідповіді, мс")
    axes[2].set_xlabel("Час від початку тесту, с")
    for ax in axes:
        ax.grid(alpha=0.3)
    axes[1].legend(frameon=False)
    axes[2].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(RES / "fig_e4_hpa.png")
    plt.close(fig)


def e5():
    rows = read_csv("e5_pod_failure.csv")
    if not rows:
        return
    emit("## E5. Відмова пода")
    n, mean, sd, lo, hi, half = stats([int(r["t_recover_ms"]) / 1000 for r in rows])
    requests = sum(int(r["requests"]) for r in rows)
    failed = sum(int(r["failed"]) for r in rows)
    table(["Показник", "Значення"],
          [["Кількість запусків", n],
           ["Час відновлення кількості готових реплік, с (середнє ± 95 % ДІ)", f"{fmt(mean)} ± {fmt(half)}"],
           ["СКВ / мін / макс, с", f"{fmt(sd)} / {fmt(lo)} / {fmt(hi)}"],
           ["Запитів усього / з помилкою", f"{requests} / {failed}"],
           ["Частка помилок, %", fmt(100 * failed / requests if requests else float('nan'), 3)]])


def bootstrap():
    path = RES / "bootstrap_times.csv"
    if not path.exists():
        return
    emit("## Час розгортання інфраструктури")
    names = {"cluster_create_ms": "Створення кластера k3d", "argocd_install_ms": "Встановлення Argo CD",
             "gitops_bootstrap_ms": "Синхронізація платформи і застосунків (app-of-apps)"}
    rows, total = [], 0.0
    for line in path.read_text().splitlines():
        key, value = line.split(",")
        rows.append([names.get(key, key), fmt(int(value) / 1000, 1)])
        total += int(value) / 1000
    rows.append(["Разом", fmt(total, 1)])
    table(["Етап", "Час, с"], rows)


if __name__ == "__main__":
    emit("# Зведені результати експериментів")
    emit()
    for step in (bootstrap, e0, e1, e2, e3, e4, e5):
        step()
    (RES / "summary.md").write_text("\n".join(OUT) + "\n", encoding="utf-8")
    print(f"\nЗбережено: {RES / 'summary.md'} та рисунки fig_*.png")
