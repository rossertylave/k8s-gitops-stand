#!/usr/bin/env python3
"""Розрахункові моделі розділу 2 пояснювальної записки.

1. Час поступового оновлення (rolling update).
2. Затримка виявлення зміни в Git при періодичному опитуванні (Argo CD).
3. Модель M/M/c (формула Ерланга C) для вибору кількості реплік.
4. Усталена кількість реплік за алгоритмом HPA.
5. Доступність сервісу з n реплік і ланцюжка сервісів.

Запуск: python3 models/models.py [каталог_для_рисунків]
"""
import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Serif", "font.size": 11, "figure.dpi": 200})
GRAYS = ["#000000", "#555555", "#888888", "#aaaaaa"]
STYLES = ["-", "--", "-.", ":"]


# ---------- 1. Rolling update ----------
def rollout_time(n: int, surge: int, t_pod: float) -> float:
    """maxUnavailable = 0: поди оновлюються партіями по surge, партія триває t_pod."""
    return math.ceil(n / surge) * t_pod


# ---------- 2. Опитування Git ----------
def poll_delay(period: float, jitter: float):
    """Середнє та максимум залишкового часу до наступного опитування.

    Довжина циклу X рівномірно розподілена на [period, period + jitter];
    зміна надходить у випадковий момент: E[R] = E[X^2] / (2 E[X]).
    """
    mean = period + jitter / 2
    var = jitter ** 2 / 12
    return (var + mean ** 2) / (2 * mean), period + jitter


# ---------- 3. M/M/c ----------
def erlang_c(c: int, a: float) -> float:
    """Імовірність очікування в черзі для M/M/c, a = lambda / mu (Ерл), a < c."""
    if a >= c:
        return 1.0
    b = 1.0  # формула Ерланга B, рекурентно
    for k in range(1, c + 1):
        b = a * b / (k + a * b)
    rho = a / c
    return b / (1 - rho * (1 - b))


def mmc_response(c: int, lam: float, mu: float) -> float:
    """Середній час перебування запиту в системі, с."""
    a = lam / mu
    if a >= c:
        return float("inf")
    return erlang_c(c, a) / (c * mu - lam) + 1 / mu


def replicas_for(lam: float, mu: float, t_max: float, c_min: int = 1) -> int:
    c = max(c_min, math.floor(lam / mu) + 1)
    while mmc_response(c, lam, mu) > t_max:
        c += 1
    return c


# ---------- 4. HPA ----------
def hpa_replicas(lam: float, cpu_per_req: float, request: float, target: float, n_min: int, n_max: int) -> int:
    """Усталена кількість реплік: сумарне споживання CPU / (request * target)."""
    need = math.ceil(lam * cpu_per_req / (request * target))
    return min(n_max, max(n_min, need))


# ---------- 5. Доступність ----------
def avail_parallel(a_pod: float, n: int) -> float:
    return 1 - (1 - a_pod) ** n


def downtime_hours_per_year(a: float) -> float:
    return (1 - a) * 8760


def main():
    data = {}

    # --- рис.: час оновлення ---
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ns = list(range(1, 13))
    for i, surge in enumerate((1, 2, 4)):
        ax.step(ns, [rollout_time(n, surge, 15) for n in ns], where="mid",
                color=GRAYS[i], ls=STYLES[i], marker="o", ms=3, label=f"maxSurge = {surge}")
    ax.set_xlabel("Кількість реплік N")
    ax.set_ylabel("Час оновлення, с")
    ax.grid(alpha=0.3)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "model_rollout.png")
    plt.close(fig)
    data["rollout"] = {f"N={n},s={s}": rollout_time(n, s, 15) for n in (2, 3, 6) for s in (1, 2)}

    # --- рис.: затримка опитування ---
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    periods = list(range(30, 301, 10))
    for i, jitter in enumerate((0, 60)):
        ax.plot(periods, [poll_delay(p, jitter)[0] for p in periods], color=GRAYS[i], ls=STYLES[i],
                label=f"середня, джитер {jitter} с")
        ax.plot(periods, [poll_delay(p, jitter)[1] for p in periods], color=GRAYS[i + 2], ls=STYLES[i + 2],
                label=f"максимальна, джитер {jitter} с")
    ax.set_xlabel("Період опитування репозиторію, с")
    ax.set_ylabel("Затримка виявлення зміни, с")
    ax.grid(alpha=0.3)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "model_poll.png")
    plt.close(fig)
    data["poll"] = {f"P={p},J={j}": [round(x, 1) for x in poll_delay(p, j)]
                    for p, j in ((120, 60), (180, 0), (60, 0), (30, 0))}

    # --- рис.: M/M/c ---
    mu = 25.0  # запитів/с на репліку (приклад: S = 40 мс)
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.5))
    lams = [x / 2 for x in range(2, 2 * 140)]
    for i, c in enumerate((2, 3, 4, 6)):
        xs = [l for l in lams if l < c * mu * 0.985]
        axes[0].plot(xs, [erlang_c(c, l / mu) for l in xs], color=GRAYS[i], ls=STYLES[i], label=f"c = {c}")
        axes[1].plot(xs, [1000 * mmc_response(c, l, mu) for l in xs], color=GRAYS[i], ls=STYLES[i], label=f"c = {c}")
    axes[0].set_ylabel("Імовірність очікування")
    axes[1].set_ylabel("Середній час відповіді, мс")
    axes[1].set_ylim(30, 200)
    for ax in axes:
        ax.set_xlabel("Інтенсивність запитів, 1/с")
        ax.grid(alpha=0.3)
        ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "model_mmc.png")
    plt.close(fig)

    rows = []
    for lam in (5, 10, 20, 30, 40, 60, 80, 100):
        c = replicas_for(lam, mu, 0.060, c_min=2)
        rows.append({"lambda": lam, "a": round(lam / mu, 2), "c": c, "rho": round(lam / (c * mu), 3),
                     "p_wait": round(erlang_c(c, lam / mu), 4),
                     "t_ms": round(1000 * mmc_response(c, lam, mu), 1),
                     "hpa": hpa_replicas(lam, 0.020, 0.25, 0.60, 2, 6)})
    data["mmc"] = rows

    # --- рис.: HPA усталений стан ---
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    lam_axis = list(range(0, 61))
    for i, target in enumerate((0.5, 0.6, 0.8)):
        ax.step(lam_axis, [hpa_replicas(l, 0.020, 0.25, target, 2, 6) for l in lam_axis], where="post",
                color=GRAYS[i], ls=STYLES[i], label=f"цільове завантаження {int(target * 100)} %")
    ax.set_xlabel("Інтенсивність запитів, 1/с")
    ax.set_ylabel("Кількість реплік")
    ax.grid(alpha=0.3)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "model_hpa.png")
    plt.close(fig)

    # --- рис.: доступність ---
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    reps = list(range(1, 7))
    for i, a_pod in enumerate((0.95, 0.99, 0.995)):
        ax.semilogy(reps, [1 - avail_parallel(a_pod, n) for n in reps], color=GRAYS[i], ls=STYLES[i],
                    marker="o", ms=3, label=f"A пода = {a_pod}")
    ax.set_xlabel("Кількість реплік n")
    ax.set_ylabel("Коефіцієнт неготовності 1 − A")
    ax.grid(alpha=0.3, which="both")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "model_avail.png")
    plt.close(fig)
    avail = []
    for n in (1, 2, 3, 4):
        a_svc = avail_parallel(0.99, n)
        a_chain = a_svc ** 2  # gateway -> catalog
        a_chain3 = a_svc ** 3  # gateway -> orders -> catalog
        avail.append({"n": n, "a_svc": round(a_svc, 8), "a_chain2": round(a_chain, 8),
                      "a_chain3": round(a_chain3, 8),
                      "down_h_chain2": round(downtime_hours_per_year(a_chain), 3),
                      "down_h_chain3": round(downtime_hours_per_year(a_chain3), 3)})
    data["avail"] = avail

    print(json.dumps(data, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
