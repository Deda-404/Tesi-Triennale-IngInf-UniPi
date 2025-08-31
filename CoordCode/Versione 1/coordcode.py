# CoordCode — proiezione pinhole con viste 2D/3D e spigoli manuali
import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

APP_TITLE = "CoordCode"
APP_DESC = ("Software didattico per determinare automaticamente le coordinate da piano 3D a piano immagine\n"
            "(modello pinhole).")

class CoordCodeApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1100x640")
        self.root.minsize(980, 560)

        # Intrinseci
        self.f = None; self.cx = None; self.cy = None

        # Dati
        self.points_3d = []     # [(X,Y,Z)]
        self.points_2d = []     # [(u,v)]
        self.manual_edges = []  # [(i,j)]  1-based indices di punti

        # Stato / viste
        self.connect_var = tk.BooleanVar(value=False)      # collega in ordine
        self.close_poly_var = tk.BooleanVar(value=False)   # chiudi poligono
        self.show_manual_var = tk.BooleanVar(value=True)   # mostra spigoli manuali
        self.view_mode = tk.StringVar(value="2D")          # "2D" | "3D"

        self.root.option_add("*Font", ("Segoe UI", 11))

        # Pagine
        self.page1 = tk.Frame(self.root); self.page2 = tk.Frame(self.root)
        self._build_page1(); self.page1.pack(fill="both", expand=True)

    # ------------------------ Pagina 1 ------------------------
    def _build_page1(self):
        frm = self.page1
        for w in frm.winfo_children(): w.destroy()
        frm.columnconfigure(0, weight=1); frm.rowconfigure(0, weight=1)

        box = tk.Frame(frm); box.grid(row=0, column=0, sticky="nsew", padx=24, pady=24)
        tk.Label(box, text="CoordCode", font=("Segoe UI Semibold", 28)).pack(pady=(4, 6))
        tk.Label(box, text=APP_DESC, wraplength=760, justify="center").pack(pady=(0, 18))

        self.f_var = tk.StringVar()
        rowf = tk.Frame(box); rowf.pack(pady=(8, 6))
        tk.Label(rowf, text="Inserisci la focale f (in pixel) e premi Invio:").pack(side="left", padx=(0,10))
        ent_f = tk.Entry(rowf, textvariable=self.f_var, width=18); ent_f.pack(side="left")
        ent_f.bind("<Return>", self._on_enter_f)

        self.cxcy_container = tk.Frame(box); self.cxcy_container.pack(pady=(10, 2))

        self.btn_next1 = ttk.Button(box, text="Avanti", command=self._on_enter_f); self.btn_next1.pack(pady=(10,2))
        tk.Label(box, text="Suggerimento: f=800, Cx=320, Cy=240", fg="#666").pack(pady=(12,0))

    def _on_enter_f(self, event=None):
        s = self.f_var.get().strip().replace(",", ".")
        try:
            fval = float(s); assert fval > 0 and math.isfinite(fval)
        except Exception:
            messagebox.showerror("Valore non valido", "Inserisci f > 0 (es. 800)."); return
        self.f = fval
        for w in self.cxcy_container.winfo_children(): w.destroy()
        tk.Label(self.cxcy_container, text="Inserisci Cx,Cy (separati da virgola) e premi Invio:").pack(side="left", padx=(0,10))
        self.cxcy_var = tk.StringVar()
        ent = tk.Entry(self.cxcy_container, textvariable=self.cxcy_var, width=18); ent.pack(side="left"); ent.focus_set()
        ent.bind("<Return>", self._on_enter_cxcy)
        self.btn_next1.configure(text="Procedi", command=self._on_enter_cxcy)

    def _on_enter_cxcy(self, event=None):
        parts = [p.strip().replace(",", ".") for p in self.cxcy_var.get().strip().split(",")]
        if len(parts) != 2:
            messagebox.showerror("Formato non corretto", "Usa Cx,Cy (es. 320,240)."); return
        try:
            self.cx, self.cy = float(parts[0]), float(parts[1])
        except Exception:
            messagebox.showerror("Valori non validi", "Cx e Cy devono essere numerici."); return
        self._show_page2()

    # ------------------------ Pagina 2 ------------------------
    def _show_page2(self):
        self.page1.forget(); self._build_page2(); self.page2.pack(fill="both", expand=True)

    def _build_page2(self):
        frm = self.page2
        for w in frm.winfo_children(): w.destroy()
        frm.columnconfigure(0, weight=1, uniform="col"); frm.columnconfigure(1, weight=1, uniform="col")
        frm.rowconfigure(0, weight=1)

        # --- Sinistra: input + tabella ---
        left = tk.Frame(frm, padx=12, pady=12); left.grid(row=0, column=0, sticky="nsew")
        tk.Label(left, text="Inserimento punti 3D", font=("Segoe UI Semibold", 14)).pack(anchor="w")
        tk.Label(left, text=f"f={self.f:.4g}, cx={self.cx:.4g}, cy={self.cy:.4g}", fg="#666").pack(anchor="w", pady=(0,8))
        tk.Label(left,
                 text="Inserisci le coordinate del punto 3D come X,Y,Z e premi Invio.\n"
                      "Ogni punto viene proiettato e numerato; puoi vedere sia la vista 2D (piano immagine) sia la vista 3D.",
                 justify="left").pack(anchor="w")

        row = tk.Frame(left); row.pack(anchor="w", pady=(8,6))
        tk.Label(row, text="Punto 3D (X,Y,Z):").pack(side="left")
        self.pt_var = tk.StringVar()
        ent = tk.Entry(row, textvariable=self.pt_var, width=28); ent.pack(side="left", padx=(8,0))
        ent.bind("<Return>", self._on_add_point)
        ttk.Button(row, text="Aggiungi", command=self._on_add_point).pack(side="left", padx=(8,0))

        columns = ("#","X","Y","Z","u","v")
        self.tree = ttk.Treeview(left, columns=columns, show="headings", height=16)
        for c in columns:
            self.tree.heading(c, text=c)
            self.tree.column(c, anchor="center", width=60 if c == "#" else 90)
        self.tree.pack(fill="both", expand=True, pady=(10,6))

        tools = tk.Frame(left); tools.pack(fill="x", pady=(2,0))
        ttk.Button(tools, text="Esporta txt…", command=self._export_txt).pack(side="left")
        ttk.Button(tools, text="Reset", command=self._reset_all).pack(side="right")

        # --- Destra: grafici + opzioni ---
        right = tk.Frame(frm, padx=12, pady=12); right.grid(row=0, column=1, sticky="nsew")
        tk.Label(right, text="Visualizzazione", font=("Segoe UI Semibold", 14)).pack(anchor="w")

        opts = tk.Frame(right); opts.pack(anchor="w", pady=(6,2))
        ttk.Radiobutton(opts, text="Vista 2D (piano immagine)", variable=self.view_mode, value="2D",
                        command=self._switch_view).pack(side="left")
        ttk.Radiobutton(opts, text="Vista 3D (piano 3D)", variable=self.view_mode, value="3D",
                        command=self._switch_view).pack(side="left", padx=(12,0))

        opts2 = tk.Frame(right); opts2.pack(anchor="w", pady=(2,4))
        ttk.Checkbutton(opts2, text="Collega punti in ordine", variable=self.connect_var,
                        command=lambda: self._redraw_current(autoscale=True)).pack(side="left")
        ttk.Checkbutton(opts2, text="Chiudi poligono", variable=self.close_poly_var,
                        command=lambda: self._redraw_current(autoscale=True)).pack(side="left", padx=(12,0))
        ttk.Checkbutton(opts2, text="Mostra spigoli manuali", variable=self.show_manual_var,
                        command=lambda: self._redraw_current(autoscale=False)).pack(side="left", padx=(12,0))

        # ---- Spigoli manuali ----
        manual = tk.LabelFrame(right, text="Collega punti (manuale)", padx=8, pady=6)
        manual.pack(fill="x", pady=(6,8))
        tk.Label(manual, text="Indica i due numeri separati da virgola (es. 6,2):").pack(side="left")
        self.edge_var = tk.StringVar()
        ent_edge = tk.Entry(manual, textvariable=self.edge_var, width=10); ent_edge.pack(side="left", padx=(8,0))
        ent_edge.bind("<Return>", self._on_add_edge)
        ttk.Button(manual, text="Collega", command=self._on_add_edge).pack(side="left", padx=(8,0))
        ttk.Button(manual, text="Annulla ultimo", command=self._undo_edge).pack(side="left", padx=(6,0))
        ttk.Button(manual, text="Svuota spigoli", command=self._clear_edges).pack(side="left", padx=(6,0))

        # Container per canvas
        self.plot_container = tk.Frame(right); self.plot_container.pack(fill="both", expand=True)

        # --- 2D ---
        self.fig2d = Figure(figsize=(5,4), dpi=100)
        self.ax2d = self.fig2d.add_subplot(111)
        self.ax2d.set_xlabel("u (pixel)"); self.ax2d.set_ylabel("v (pixel)")
        self.ax2d.grid(True, alpha=0.25)
        self.ax2d.plot(self.cx, self.cy, marker="+", markersize=12, linestyle="None", label="Principal point")
        self.ax2d.legend(loc="best")
        self.canvas2d = FigureCanvasTkAgg(self.fig2d, master=self.plot_container)
        self.canvas2d_widget = self.canvas2d.get_tk_widget()
        self.toolbar2d = NavigationToolbar2Tk(self.canvas2d, right); self.toolbar2d.update()

        # --- 3D ---
        self.fig3d = Figure(figsize=(5,4), dpi=100)
        self.ax3d = self.fig3d.add_subplot(111, projection="3d")
        self.ax3d.set_xlabel("X"); self.ax3d.set_ylabel("Y"); self.ax3d.set_zlabel("Z")
        self.ax3d.grid(True)
        try: self.ax3d.set_box_aspect((1,1,1))
        except Exception: pass
        self.canvas3d = FigureCanvasTkAgg(self.fig3d, master=self.plot_container)
        self.canvas3d_widget = self.canvas3d.get_tk_widget()
        self.toolbar3d = NavigationToolbar2Tk(self.canvas3d, right); self.toolbar3d.update()

        # Mostra inizialmente 2D
        self._show_2d_widgets()
        self.status = tk.Label(frm, text="", anchor="w", fg="#555")
        self.status.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0,8))

    # ------------------------ Azioni base ------------------------
    def _project_point(self, X, Y, Z):
        if Z <= 0: raise ValueError("Z deve essere > 0 (il punto deve trovarsi davanti alla camera).")
        u = self.f * (X / Z) + self.cx
        v = self.f * (Y / Z) + self.cy
        return u, v

    def _on_add_point(self, event=None):
        raw = self.pt_var.get().strip()
        parts = [p.strip().replace(",", ".") for p in raw.split(",")]
        if len(parts) != 3:
            messagebox.showerror("Formato non corretto", "Usa X,Y,Z (es. 0,200,2000)."); return
        try:
            X, Y, Z = map(float, parts)
            assert all(map(math.isfinite, (X, Y, Z)))
        except Exception:
            messagebox.showerror("Valori non validi", "X, Y, Z devono essere numerici."); return

        try:
            u, v = self._project_point(X, Y, Z)
        except Exception as e:
            messagebox.showerror("Proiezione non valida", str(e)); return

        self.points_3d.append((X, Y, Z)); self.points_2d.append((u, v))
        idx = len(self.points_2d)
        self.tree.insert("", "end",
                         values=(idx, f"{X:.6g}", f"{Y:.6g}", f"{Z:.6g}", f"{u:.4f}", f"{v:.4f}"))
        self.pt_var.set("")
        self.status.configure(text=f"Aggiunto #{idx}  P=({X}, {Y}, {Z})  ->  p=({u:.2f}, {v:.2f})")
        self._redraw_current(autoscale=True)

    # ------------------------ Spigoli manuali ------------------------
    def _on_add_edge(self, event=None):
        if len(self.points_2d) < 2:
            messagebox.showinfo("Pochi punti", "Inserisci almeno due punti prima di collegarli."); return
        s = self.edge_var.get().strip()
        if not s:
            messagebox.showerror("Input mancante", "Indica i due numeri separati da virgola (es. 6,2)."); return
        parts = [p.strip() for p in s.split(",")]
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            messagebox.showerror("Formato non corretto", "Usa due interi separati da virgola (es. 6,2)."); return
        i, j = map(int, parts)
        n = len(self.points_2d)
        if not (1 <= i <= n and 1 <= j <= n):
            messagebox.showerror("Indici non validi", f"Gli indici devono essere tra 1 e {n}."); return
        if i == j:
            messagebox.showerror("Indici identici", "Scegli due punti diversi."); return

        # Evita duplicati (trattiamo l'arco non orientato)
        key = (min(i, j), max(i, j))
        if key in self.manual_edges:
            messagebox.showinfo("Già presente", f"Lo spigolo {i}-{j} è già stato aggiunto."); return

        self.manual_edges.append(key)
        self.edge_var.set("")
        self.status.configure(text=f"Collegati i punti {i} e {j}.")
        self._redraw_current(autoscale=False)

    def _undo_edge(self):
        if not self.manual_edges:
            messagebox.showinfo("Nessuno spigolo", "Non ci sono spigoli manuali da annullare."); return
        last = self.manual_edges.pop()
        self.status.configure(text=f"Rimosso ultimo spigolo {last[0]}-{last[1]}.")
        self._redraw_current(autoscale=False)

    def _clear_edges(self):
        if not self.manual_edges: return
        self.manual_edges.clear()
        self.status.configure(text="Spigoli manuali svuotati.")
        self._redraw_current(autoscale=False)

    # ------------------------ Redraw helpers ------------------------
    def _poly_coords(self, coords, close=False):
        if not coords: return []
        return (list(coords) + [coords[0]]) if (close and len(coords) >= 3) else list(coords)

    def _redraw_current(self, autoscale=False):
        if self.view_mode.get() == "2D": self._redraw_2d(autoscale)
        else: self._redraw_3d(autoscale)

    def _redraw_2d(self, autoscale=False):
        ax = self.ax2d; ax.clear()
        ax.set_xlabel("u (pixel)"); ax.set_ylabel("v (pixel)")
        ax.grid(True, alpha=0.25)
        ax.plot(self.cx, self.cy, marker="+", markersize=12, linestyle="None", label="Principal point")

        # Punti + numerazione
        if self.points_2d:
            us, vs = zip(*self.points_2d)
            ax.plot(us, vs, "o", linestyle="None", zorder=3)
            for k, (u, v) in enumerate(self.points_2d, start=1):
                ax.annotate(str(k), (u, v), textcoords="offset points", xytext=(4,4),
                            fontsize=9, color="#444", zorder=4)

        # Collegamento automatico
        if self.connect_var.get() and len(self.points_2d) >= 2:
            pts = self._poly_coords(self.points_2d, self.close_poly_var.get())
            xs, ys = zip(*pts); ax.plot(xs, ys, "-", linewidth=1.6, zorder=2)

        # Spigoli manuali (linea tratteggiata)
        if self.show_manual_var.get():
            for (i, j) in self.manual_edges:
                (u1, v1) = self.points_2d[i-1]; (u2, v2) = self.points_2d[j-1]
                ax.plot([u1, u2], [v1, v2], linestyle="--", linewidth=1.8, zorder=2)

        ax.legend(loc="best")
        if autoscale: self._autoscale2d(ax)
        self.canvas2d.draw_idle()

    def _autoscale2d(self, ax, margin_ratio=0.10):
        ax.relim(); ax.autoscale_view()
        x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
        dx = (x1 - x0) or 1.0; dy = (y1 - y0) or 1.0
        mx = dx * margin_ratio; my = dy * margin_ratio
        ax.set_xlim(x0 - mx, x1 + mx); ax.set_ylim(y0 - my, y1 + my)

    def _redraw_3d(self, autoscale=False):
        ax = self.ax3d; ax.clear()
        ax.set_xlabel("X"); ax.set_ylabel("Y"); ax.set_zlabel("Z")
        ax.grid(True)

        # Punti + numerazione
        if self.points_3d:
            xs, ys, zs = zip(*self.points_3d)
            ax.scatter(xs, ys, zs, s=30, depthshade=True)
            for k, (x, y, z) in enumerate(self.points_3d, start=1):
                ax.text(x, y, z, str(k), fontsize=9, color="#333")

        # Collegamento automatico
        if self.connect_var.get() and len(self.points_3d) >= 2:
            pts = self._poly_coords(self.points_3d, self.close_poly_var.get())
            xs, ys, zs = zip(*pts); ax.plot(xs, ys, zs, linewidth=1.6)

        # Spigoli manuali
        if self.show_manual_var.get():
            for (i, j) in self.manual_edges:
                (x1, y1, z1) = self.points_3d[i-1]; (x2, y2, z2) = self.points_3d[j-1]
                ax.plot([x1, x2], [y1, y2], [z1, z2], linestyle="--", linewidth=1.8)

        if autoscale: self._autoscale3d(ax)
        try: ax.set_box_aspect((1,1,1))
        except Exception: pass
        self.canvas3d.draw_idle()

    def _autoscale3d(self, ax, margin_ratio=0.10):
        if not self.points_3d:
            ax.set_xlim(-1, 1); ax.set_ylim(-1, 1); ax.set_zlim(0, 2); return
        xs, ys, zs = zip(*self.points_3d)
        mins = [min(xs), min(ys), min(zs)]; maxs = [max(xs), max(ys), max(zs)]
        ranges = [mx - mn for mx, mn in zip(maxs, mins)]
        max_range = max(ranges) or 1.0
        cx = (max(xs) + min(xs)) / 2.0; cy = (max(ys) + min(ys)) / 2.0; cz = (max(zs) + min(zs)) / 2.0
        half = max_range / 2.0; m = max_range * margin_ratio
        ax.set_xlim(cx - half - m, cx + half + m)
        ax.set_ylim(cy - half - m, cy + half + m)
        ax.set_zlim(cz - half - m, cz + half + m)

    # ------------------------ UI helpers ------------------------
    def _show_2d_widgets(self):
        try: self.canvas3d_widget.pack_forget(); self.toolbar3d.pack_forget()
        except Exception: pass
        self.canvas2d_widget.pack(fill="both", expand=True)
        self.toolbar2d.pack(side="bottom", fill="x")
        self._redraw_2d(autoscale=True)

    def _show_3d_widgets(self):
        try: self.canvas2d_widget.pack_forget(); self.toolbar2d.pack_forget()
        except Exception: pass
        self.canvas3d_widget.pack(fill="both", expand=True)
        self.toolbar3d.pack(side="bottom", fill="x")
        self._redraw_3d(autoscale=True)

    def _switch_view(self):
        self._show_2d_widgets() if self.view_mode.get() == "2D" else self._show_3d_widgets()

    # ------------------------ Varie ------------------------
    def _reset_all(self):
        self.points_3d.clear(); self.points_2d.clear(); self.manual_edges.clear()
        for i in self.tree.get_children(): self.tree.delete(i)
        self._redraw_current(autoscale=True); self.status.configure(text="")

    def _export_txt(self):
        if not self.points_3d:
            messagebox.showinfo("Nessun dato", "Non ci sono punti da esportare."); return
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                            filetypes=[("txt","*.txt"), ("Tutti i file","*.*")],
                                            title="Esporta dati come txt")
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("# i,X,Y,Z,u,v\n")
                for i, ((X,Y,Z),(u,v)) in enumerate(zip(self.points_3d, self.points_2d), start=1):
                    f.write(f"{i},{X},{Y},{Z},{u},{v}\n")
                if self.manual_edges:
                    f.write("# manual_edges: i,j\n")
                    for (i,j) in self.manual_edges:
                        f.write(f"{i},{j}\n")
            messagebox.showinfo("Esportazione completata", f"Dati salvati in:\n{path}")
        except Exception as e:
            messagebox.showerror("Errore di scrittura", str(e))

def main():
    root = tk.Tk()
    app = CoordCodeApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
