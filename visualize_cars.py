import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import numpy as np
from scipy.stats import gaussian_kde

# ── load data ────────────────────────────────────────────────────────────────

DATA = Path(__file__).parent / "cars_output.csv"

def parse_price(s):
    m = re.sub(r"[^\d.]", "", s)
    return float(m) if m else None

with open(DATA, encoding="utf-8") as f:
    raw = list(csv.DictReader(f))

rows = []
for r in raw:
    price = parse_price(r["Price"])
    msrp  = parse_price(r["MSRP"])
    if price and msrp:
        rows.append({**r, "_price": price, "_msrp": msrp,
                     "_savings": msrp - price})

# ── style ────────────────────────────────────────────────────────────────────

sns.set_theme(style="whitegrid", palette="muted", font_scale=1.05)
ACCENT = "#2563EB"
fig = plt.figure(figsize=(20, 18))
fig.suptitle("New Car Listings — CarGurus Data", fontsize=18, fontweight="bold")
gs = fig.add_gridspec(3, 2, hspace=0.55, wspace=0.38,
                      top=0.95, bottom=0.05, left=0.07, right=0.97)

# ── 1. Listing count by model (top 15) ───────────────────────────────────────

ax1 = fig.add_subplot(gs[0, :])
model_counts = Counter(r["Title"] for r in rows)
top_models = model_counts.most_common(15)
labels, counts = zip(*top_models)
short = [l.replace("2025 ", "").replace("2024 ", "") for l in labels]
colors = sns.color_palette("Blues_d", len(counts))
bars = ax1.barh(short[::-1], counts[::-1], color=colors[::-1], edgecolor="white")
ax1.bar_label(bars, padding=4, fontsize=9)
ax1.set_xlabel("Number of Listings")
ax1.set_title("Top 15 Car Models by Listing Count", fontweight="bold")
ax1.set_xlim(0, max(counts) * 1.15)

# ── 2. Price distribution (histogram + KDE) ───────────────────────────────────

ax2 = fig.add_subplot(gs[1, 0])
prices = [r["_price"] for r in rows]
ax2.hist(prices, bins=30, color=ACCENT, alpha=0.75, edgecolor="white", density=True)
kde_x = np.linspace(min(prices), max(prices), 300)
kde = gaussian_kde(prices)
ax2.plot(kde_x, kde(kde_x), color="#DC2626", linewidth=2, label="KDE")
ax2.axvline(np.mean(prices), color="#16A34A", linewidth=1.8, linestyle="--",
            label=f"Mean ${np.mean(prices):,.0f}")
ax2.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
ax2.set_xlabel("Listed Price")
ax2.set_ylabel("Density")
ax2.set_title("Price Distribution", fontweight="bold")
ax2.legend(fontsize=9)

# ── 3. Avg price by model (top 12) ───────────────────────────────────────────

ax3 = fig.add_subplot(gs[1, 1])
price_by_model = defaultdict(list)
for r in rows:
    price_by_model[r["Title"].replace("2025 ", "").replace("2024 ", "")].append(r["_price"])

avg_prices = {m: np.mean(v) for m, v in price_by_model.items() if len(v) >= 5}
sorted_avg = sorted(avg_prices.items(), key=lambda x: x[1])[:12]
m_labels, m_avgs = zip(*sorted_avg)
palette = sns.color_palette("RdYlGn", len(m_avgs))
b = ax3.barh(m_labels, m_avgs, color=palette, edgecolor="white")
ax3.bar_label(b, labels=[f"${v:,.0f}" for v in m_avgs], padding=4, fontsize=8)
ax3.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
ax3.set_xlabel("Average Listed Price")
ax3.set_title("Avg Price by Model (min 5 listings)", fontweight="bold")
ax3.set_xlim(0, max(m_avgs) * 1.18)

# ── 4. MSRP vs Price scatter ──────────────────────────────────────────────────

ax4 = fig.add_subplot(gs[2, 0])
msrps  = [r["_msrp"]  for r in rows]
listed = [r["_price"] for r in rows]
savings = [r["_savings"] for r in rows]
sc = ax4.scatter(msrps, listed, c=savings, cmap="RdYlGn", alpha=0.55,
                 s=25, edgecolors="none")
mn, mx = min(msrps + listed), max(msrps + listed)
ax4.plot([mn, mx], [mn, mx], "k--", linewidth=1, alpha=0.4, label="MSRP = Price")
cb = plt.colorbar(sc, ax=ax4)
cb.set_label("Savings ($)", fontsize=9)
cb.formatter = mticker.FuncFormatter(lambda x, _: f"${x:,.0f}")
cb.update_ticks()
ax4.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
ax4.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
ax4.set_xlabel("MSRP")
ax4.set_ylabel("Listed Price")
ax4.set_title("MSRP vs Listed Price\n(green = more savings)", fontweight="bold")
ax4.legend(fontsize=9)

# ── 5. Top 10 dealer locations ────────────────────────────────────────────────

ax5 = fig.add_subplot(gs[2, 1])
loc_counts = Counter(r["Location"] for r in rows)
top_locs = loc_counts.most_common(10)
l_labels, l_counts = zip(*top_locs)
wedge_colors = sns.color_palette("tab10", len(l_counts))
wedges, texts, autotexts = ax5.pie(
    l_counts, labels=None, autopct="%1.1f%%", startangle=140,
    colors=wedge_colors, pctdistance=0.78,
    wedgeprops=dict(edgecolor="white", linewidth=1.5)
)
for at in autotexts:
    at.set_fontsize(8)
ax5.legend(wedges, [f"{l} ({c})" for l, c in zip(l_labels, l_counts)],
           loc="lower left", bbox_to_anchor=(-0.25, -0.15), fontsize=8,
           framealpha=0.9)
ax5.set_title("Top 10 Dealer Locations", fontweight="bold")

# ── save ──────────────────────────────────────────────────────────────────────

out = Path(__file__).parent / "cars_dashboard.png"
fig.savefig(out, dpi=150, bbox_inches="tight")
print(f"Saved -> {out}")
plt.show()
