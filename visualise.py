"""
Interactive visualiser for the mine truck routing solution.

Usage: call visualise.show(sol) where sol = visualise.extract(X, Y, Z, Jobs, S, D, T, data)
  X     – Gurobi vars X[j, t], 1 if job j starts at time t
  Y     – Gurobi vars Y[s, t], trucks queued at Shovel s at time t
  Z     – Gurobi vars Z[d, t], trucks queued at Dump d at time t
  Jobs  – set of Job objects
  S     – list of Shovel objects
  D     – list of Dump objects
  T     – time-step range
  data  – raw JSON data dict
"""

import math
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.widgets import Slider, Button
import numpy as np

from mine_site_classes import TruckState

# ── Colours ────────────────────────────────────────────────────────────────────
C_SHOVEL   = "#2ecc71"
C_DUMP     = "#e74c3c"
C_LOADED   = "#3498db"
C_EMPTY    = "#95a5a6"
C_LOADING  = "#f1c40f"
C_UNLOAD   = "#e67e22"
C_GRID     = "#dddddd"


# ── Solution extraction ─────────────────────────────────────────────────────────

def extract(X, Y, Z, Jobs, S, D, T, data):
    """
    Convert Gurobi solution variables into plain Python data for visualisation.

    Job phases:
      Loaded  (Shovel→Dump): [t … t+travel_loaded)  traveling,  [t+travel_loaded … t+dur)  unloading
      Unloaded (Dump→Shovel): [t … t+travel_empty)   traveling,  [t+travel_empty  … t+dur)  loading
    """
    speed_loaded  = data["speed_loaded_kph"]
    speed_empty   = data["speed_unloaded_kph"]
    loading_min   = data["loading_time_min"]
    unloading_min = data["unloading_time_min"]

    jobs_out = []
    for (j, t), var in X.items():
        if round(var.x) != 1:
            continue

        if j.truck_state == TruckState.LOADED:
            src_type, dst_type = "S", "D"
            travel_time = math.ceil((j.distance / speed_loaded) * 60 / 1000)
            op_time     = unloading_min
            loaded      = True
        else:
            src_type, dst_type = "D", "S"
            travel_time = math.ceil((j.distance / speed_empty) * 60 / 1000)
            op_time     = loading_min
            loaded      = False

        jobs_out.append(dict(
            t0=t, t1=t + j.duration, t_op=t + travel_time,
            src_type=src_type, src=j.source,
            dst_type=dst_type, dst=j.destination,
            travel_time=travel_time, op_time=op_time,
            loaded=loaded,
        ))

    T_list = list(T)
    return dict(
        jobs    = jobs_out,
        queue_S = {(s, t): max(0, round(Y[s, t].x)) for s in S for t in T_list},
        queue_D = {(d, t): max(0, round(Z[d, t].x)) for d in D for t in T_list},
        S       = S,
        D       = D,
        T_max   = max(T_list),
        data    = data,
    )


# ── Layout helpers ─────────────────────────────────────────────────────────────

def _node_positions(S, D):
    pos = {}
    for i, s in enumerate(S):
        pos[("S", s)] = (0.12, (i + 0.5) / len(S))
    for i, d in enumerate(D):
        pos[("D", d)] = (0.88, (i + 0.5) / len(D))
    return pos


# ── Main visualiser ─────────────────────────────────────────────────────────────

def show(sol):
    jobs  = sol["jobs"]
    qS    = sol["queue_S"]
    qD    = sol["queue_D"]
    S     = sol["S"]   # list of Shovel objects
    D     = sol["D"]   # list of Dump objects
    T_max = sol["T_max"]

    pos = _node_positions(S, D)

    # ── Figure layout ────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(17, 10))
    fig.patch.set_facecolor("#f8f9fa")
    gs  = gridspec.GridSpec(
        3, 1, figure=fig,
        height_ratios=[5, 2, 0.25],
        hspace=0.38, left=0.04, right=0.97, top=0.95, bottom=0.07,
    )
    ax_net    = fig.add_subplot(gs[0])
    ax_queue  = fig.add_subplot(gs[1])
    ax_slider = fig.add_subplot(gs[2])

    ax_net.axis("off")
    ax_net.set_facecolor("#f8f9fa")
    ax_queue.set_facecolor("#f8f9fa")
    ax_queue.set_xlabel("Time (min)", fontsize=9)
    ax_queue.set_ylabel("Trucks queued", fontsize=9)
    ax_queue.set_xlim(0, T_max)
    ax_queue.tick_params(labelsize=8)

    slider = Slider(ax_slider, "t (min)", 0, T_max, valinit=0, valstep=1,
                    color="#3498db")

    # Pre-build queue timeseries
    T_arr = np.arange(T_max + 1)
    queue_lines = {}
    shovel_colors = plt.cm.Greens(np.linspace(0.5, 0.9, len(S)))
    dump_colors   = plt.cm.Reds  (np.linspace(0.5, 0.9, len(D)))

    for idx, s in enumerate(S):
        vals = [qS.get((s, t), 0) for t in T_arr]
        (ln,) = ax_queue.plot(T_arr, vals, color=shovel_colors[idx],
                              lw=1.3, label=f"S{s.site_id}")
        queue_lines[("S", s)] = ln

    for idx, d in enumerate(D):
        vals = [qD.get((d, t), 0) for t in T_arr]
        (ln,) = ax_queue.plot(T_arr, vals, color=dump_colors[idx],
                              lw=1.3, linestyle="--", label=f"D{d.site_id}")
        queue_lines[("D", d)] = ln

    ax_queue.legend(loc="upper right", fontsize=7, ncol=3, framealpha=0.85)
    q_vline = ax_queue.axvline(x=0, color="#e74c3c", lw=1.4, alpha=0.8)

    # ── Draw function ────────────────────────────────────────────────────────
    def _draw(t):
        t = int(t)
        ax_net.clear()
        ax_net.set_xlim(0, 1)
        ax_net.set_ylim(-0.08, 1.1)
        ax_net.axis("off")
        ax_net.set_title(f"Mine Fleet  —  t = {t} min", fontsize=13, pad=8)

        # Background arcs
        for s in S:
            for d in D:
                p1, p2 = pos[("S", s)], pos[("D", d)]
                ax_net.plot([p1[0], p2[0]], [p1[1], p2[1]],
                            color=C_GRID, lw=0.7, zorder=1)

        # Classify active jobs at time t
        traveling = [j for j in jobs if j["t0"] <= t < j["t_op"]]
        operating = [j for j in jobs if j["t_op"] <= t < j["t1"]]

        # Active arc highlights + moving truck dots
        for j in traveling:
            p1 = pos[(j["src_type"], j["src"])]
            p2 = pos[(j["dst_type"], j["dst"])]
            color = C_LOADED if j["loaded"] else C_EMPTY
            ax_net.plot([p1[0], p2[0]], [p1[1], p2[1]],
                        color=color, lw=2, alpha=0.55, zorder=2)
            frac = (t - j["t0"]) / max(j["travel_time"], 1)
            tx   = p1[0] + frac * (p2[0] - p1[0])
            ty   = p1[1] + frac * (p2[1] - p1[1])
            ax_net.plot(tx, ty, "o", color=color, ms=13, zorder=5,
                        mec="white", mew=1.8)

        # Pulsing rings for loading / unloading at destination nodes
        op_nodes = {}
        for j in operating:
            key   = (j["dst_type"], j["dst"])
            color = C_LOADING if not j["loaded"] else C_UNLOAD
            op_nodes[key] = color

        for (ntype, node), color in op_nodes.items():
            cx, cy = pos[(ntype, node)]
            ring = plt.Circle((cx, cy), 0.065, color=color, fill=False,
                              lw=3.5, zorder=6)
            ax_net.add_patch(ring)

        # Nodes
        for s in S:
            cx, cy = pos[("S", s)]
            ax_net.add_patch(plt.Circle((cx, cy), 0.048,
                             color=C_SHOVEL, zorder=4))
            q = qS.get((s, t), 0)
            ax_net.text(cx, cy, str(q), ha="center", va="center",
                        fontsize=9, fontweight="bold", color="white", zorder=7)
            ax_net.text(cx, cy + 0.07, f"S{s.site_id}", ha="center", va="bottom",
                        fontsize=9, fontweight="bold", color="#1a5c35")

        for d in D:
            cx, cy = pos[("D", d)]
            ax_net.add_patch(plt.Circle((cx, cy), 0.048,
                             color=C_DUMP, zorder=4))
            q = qD.get((d, t), 0)
            ax_net.text(cx, cy, str(q), ha="center", va="center",
                        fontsize=9, fontweight="bold", color="white", zorder=7)
            ax_net.text(cx, cy + 0.07, f"D{d.site_id}", ha="center", va="bottom",
                        fontsize=9, fontweight="bold", color="#7b1a1a")

        # Column labels
        ax_net.text(0.12, 1.06, "Shovels", ha="center", va="bottom",
                    fontsize=11, fontweight="bold", color="#1a5c35")
        ax_net.text(0.88, 1.06, "Dumps", ha="center", va="bottom",
                    fontsize=11, fontweight="bold", color="#7b1a1a")

        # Legend
        handles = [
            mpatches.Patch(color=C_SHOVEL,  label="Shovel (number = queue)"),
            mpatches.Patch(color=C_DUMP,    label="Dump   (number = queue)"),
            mpatches.Patch(color=C_LOADED,  label="Traveling loaded"),
            mpatches.Patch(color=C_EMPTY,   label="Traveling empty"),
            mpatches.Patch(color=C_LOADING, label="Loading"),
            mpatches.Patch(color=C_UNLOAD,  label="Unloading"),
        ]
        ax_net.legend(handles=handles, loc="lower center", ncol=3,
                      fontsize=8, framealpha=0.9,
                      bbox_to_anchor=(0.5, -0.04))

        q_vline.set_xdata([t, t])
        fig.canvas.draw_idle()

    slider.on_changed(_draw)

    # ── Play / Pause ─────────────────────────────────────────────────────────
    playing = [False]
    timer   = [None]

    ax_btn = plt.axes([0.91, 0.025, 0.07, 0.028])
    btn    = Button(ax_btn, "▶  Play", color="#ecf0f1", hovercolor="#bdc3c7")
    btn.label.set_fontsize(9)

    def _tick():
        if not playing[0]:
            return
        nxt = min(int(slider.val) + 1, T_max)
        slider.set_val(nxt)
        if nxt >= T_max:
            playing[0] = False
            btn.label.set_text("▶  Play")

    def _toggle(event):
        playing[0] = not playing[0]
        if playing[0]:
            btn.label.set_text("⏸  Pause")
            t_obj = fig.canvas.new_timer(interval=60)
            t_obj.add_callback(_tick)
            t_obj.start()
            timer[0] = t_obj
        else:
            btn.label.set_text("▶  Play")
            if timer[0]:
                timer[0].stop()

    btn.on_clicked(_toggle)

    _draw(0)
    plt.show()
