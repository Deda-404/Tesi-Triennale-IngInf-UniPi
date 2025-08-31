# =============================================================================
#  CoordCode — Strumento didattico per proiezione pinhole con viste 2D/3D
#  Autore: Alessio de Dato - Ingegneria Informatica UniPi
#
#  DESCRIZIONE GENERALE
#  --------------------
#  L'applicazione consente di:
#   • Inserire punti 3D (X,Y,Z), proiettarli sul piano immagine (u,v) con il modello pinhole
#     (u = f*X/Z + cx,  v = f*Y/Z + cy).
#   • Visualizzare sia la vista 2D (piano immagine) sia la vista 3D (piano dei punti 3D),
#     con zoom e pan tramite toolbar di Matplotlib.
#   • Collegare i punti automaticamente in ordine (con opzione “chiudi poligono”).
#   • Aggiungere “spigoli manuali” tra qualunque coppia di punti (i, j).
#   • Esportare e importare dati da/verso file .txt con struttura leggibile in italiano.
#
#  ORGANIZZAZIONE DEL CODICE
#  -------------------------
#   • Classe ApplicazioneCoordCode:
#       - __init__                : inizializza stato, pagine e stili GUI.
#       - costruisci_pagina1      : prima pagina (inserimento f, Cx, Cy).
#       - conferma_f              : validazione focale e transizione ai campi Cx,Cy.
#       - conferma_cx_cy          : validazione Cx,Cy e transizione alla pagina 2.
#       - mostra_pagina2 / costruisci_pagina2
#                                : seconda pagina (inserimento punti, tabella, grafici e opzioni).
#       - proietta_punto          : calcolo (u,v) dal punto 3D (X,Y,Z).
#       - aggiungi_punto          : parsing input X,Y,Z, proiezione e aggiornamento UI.
#       - aggiungi_spigolo        : aggiunge collegamento manuale (i,j).
#       - annulla_spigolo         : rimuove l’ultimo collegamento manuale.
#       - svuota_spigoli          : cancella tutti i collegamenti manuali.
#       - coord_polilinea         : utilità per ottenere lista di punti con eventuale chiusura.
#       - ridisegna_corrente      : dispatch verso ridisegna_2d o ridisegna_3d.
#       - ridisegna_2d / ridisegna_3d
#                                : aggiornano rispettivamente vista 2D/3D (punti, etichette, linee).
#       - autoscale_2d / autoscale_3d
#                                : adattano i limiti degli assi con margine.
#       - mostra_vista_2d / mostra_vista_3d / cambia_vista
#                                : gestione dello switch di vista e toolbar.
#       - reset_totale            : pulizia completa di punti, spigoli e tabella.
#       - esporta_txt             : salvataggio su file .txt (formato descrittivo in italiano).
#       - importa_txt             : carica da file .txt (camera, punti e spigoli) e ridisegna le viste.
# =============================================================================

import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  # necessario per attivare il backend 3D

TITOLO_APP = "CoordCode"
DESCRIZIONE_APP = (
    "Software didattico per determinare automaticamente le coordinate da piano 3D "
    "a piano immagine (modello pinhole)."
)


class ApplicazioneCoordCode:
    """Controller principale dell'applicazione.

    Si occupa di:
    - gestire lo stato (parametri intrinseci, punti 3D/2D, spigoli manuali),
    - costruire e aggiornare la GUI Tkinter,
    - disegnare le viste 2D/3D con Matplotlib,
    - importare/esportare i dati.
    """

    # ------------------------------------------------------------------ #
    # COSTRUZIONE E NAVIGAZIONE DELLE PAGINE
    # ------------------------------------------------------------------ #
    def __init__(self, radice: tk.Tk) -> None:
        """Inizializza la finestra principale, lo stato e costruisce la pagina 1."""
        self.radice = radice
        self.radice.title(TITOLO_APP)
        self.radice.geometry("1100x640")
        self.radice.minsize(980, 560)
        self.radice.option_add("*Font", ("Segoe UI", 11))

        # Parametri intrinseci della camera (f, cx, cy)
        self.focale: float | None = None
        self.cx: float | None = None
        self.cy: float | None = None

        # Dataset principale
        self.punti_3d: list[tuple[float, float, float]] = []   # lista di (X,Y,Z)
        self.punti_2d: list[tuple[float, float]] = []          # lista di (u,v) proiettati
        self.spigoli_manuali: list[tuple[int, int]] = []       # lista di (i,j) 1-based

        # Stato di visualizzazione
        self.collega_in_ordine_var = tk.BooleanVar(value=False)   # collega in ordine di inserimento
        self.chiudi_poligono_var = tk.BooleanVar(value=False)     # collega anche ultimo->primo
        self.mostra_spigoli_manuali_var = tk.BooleanVar(value=True)
        self.modalita_vista = tk.StringVar(value="2D")            # "2D" oppure "3D"

        # Variabili/UI condivise
        self.var_intrinseci_testo = tk.StringVar()
        self.var_punto = tk.StringVar()
        self.var_spigolo = tk.StringVar()
        self.etichetta_stato: tk.Label | None = None
        self.albero_punti: ttk.Treeview | None = None

        # Oggetti Matplotlib (inizializzati in costruisci_pagina2)
        self.figura_2d = self.assi_2d = self.canvas_2d = self.widget_canvas_2d = self.toolbar_2d = None
        self.figura_3d = self.assi_3d = self.canvas_3d = self.widget_canvas_3d = self.toolbar_3d = None

        # Contenitori-pagina
        self.pagina1 = tk.Frame(self.radice)
        self.pagina2 = tk.Frame(self.radice)

        # Avvio con pagina 1
        self.costruisci_pagina1()
        self.pagina1.pack(fill="both", expand=True)

    def costruisci_pagina1(self) -> None:
        """Costruisce la schermata iniziale per l'inserimento di f, Cx, Cy."""
        frame = self.pagina1
        for w in frame.winfo_children():
            w.destroy()
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        contenitore = tk.Frame(frame)
        contenitore.grid(row=0, column=0, sticky="nsew", padx=24, pady=24)

        tk.Label(contenitore, text="CoordCode", font=("Segoe UI Semibold", 28)).pack(pady=(4, 6))
        tk.Label(contenitore, text=DESCRIZIONE_APP, wraplength=760, justify="center").pack(pady=(0, 18))

        # Input focale f
        self.var_focale = tk.StringVar()
        riga_f = tk.Frame(contenitore)
        riga_f.pack(pady=(8, 6))
        tk.Label(riga_f, text="Inserisci la focale f (in pixel) e premi Invio:").pack(side="left", padx=(0, 10))
        ingresso_f = tk.Entry(riga_f, textvariable=self.var_focale, width=18)
        ingresso_f.pack(side="left")
        ingresso_f.bind("<Return>", self.conferma_f)

        # Placeholder per i campi Cx,Cy (appaiono dopo f valida)
        self.contenitore_cxcy = tk.Frame(contenitore)
        self.contenitore_cxcy.pack(pady=(10, 2))

        self.pulsante_avanti = ttk.Button(contenitore, text="Avanti", command=self.conferma_f)
        self.pulsante_avanti.pack(pady=(10, 2))

        tk.Label(contenitore, text="Suggerimento: f=800, Cx=320, Cy=240", fg="#666").pack(pady=(12, 0))

    def conferma_f(self, _evento=None) -> None:
        """Valida la focale; se corretta, mostra i campi per Cx e Cy."""
        testo = self.var_focale.get().strip().replace(",", ".")
        try:
            valore = float(testo)
            if not (math.isfinite(valore) and valore > 0):
                raise ValueError
        except Exception:
            messagebox.showerror("Valore non valido", "Inserisci f > 0 (es. 800).")
            return

        self.focale = valore

        # Attiva la seconda riga di inserimento (Cx,Cy)
        for w in self.contenitore_cxcy.winfo_children():
            w.destroy()
        tk.Label(self.contenitore_cxcy, text="Inserisci Cx,Cy (separati da virgola) e premi Invio:").pack(
            side="left", padx=(0, 10)
        )
        self.var_cxcy = tk.StringVar()
        ingresso_cxcy = tk.Entry(self.contenitore_cxcy, textvariable=self.var_cxcy, width=18)
        ingresso_cxcy.pack(side="left")
        ingresso_cxcy.focus_set()
        ingresso_cxcy.bind("<Return>", self.conferma_cx_cy)
        self.pulsante_avanti.configure(text="Procedi", command=self.conferma_cx_cy)

    def conferma_cx_cy(self, _evento=None) -> None:
        """Valida Cx,Cy; se corretti, passa alla pagina operativa (pagine 2)."""
        parti = [p.strip().replace(",", ".") for p in self.var_cxcy.get().strip().split(",")]
        if len(parti) != 2:
            messagebox.showerror("Formato non corretto", "Usa Cx,Cy (es. 320,240).")
            return
        try:
            self.cx, self.cy = float(parti[0]), float(parti[1])
        except Exception:
            messagebox.showerror("Valori non validi", "Cx e Cy devono essere numerici.")
            return

        self.mostra_pagina2()

    def mostra_pagina2(self) -> None:
        """Nasconde la pagina 1, costruisce e visualizza la pagina 2."""
        self.pagina1.forget()
        self.costruisci_pagina2()
        self.pagina2.pack(fill="both", expand=True)

    def costruisci_pagina2(self) -> None:
        """Pagina operativa: input punti, tabella, viste 2D/3D, collegamenti e import/export."""
        frame = self.pagina2
        for w in frame.winfo_children():
            w.destroy()

        frame.columnconfigure(0, weight=1, uniform="col")
        frame.columnconfigure(1, weight=1, uniform="col")
        frame.rowconfigure(0, weight=1)

        # ------------------ COLONNA SINISTRA (input + tabella) ------------------
        sinistra = tk.Frame(frame, padx=12, pady=12)
        sinistra.grid(row=0, column=0, sticky="nsew")

        tk.Label(sinistra, text="Inserimento punti 3D", font=("Segoe UI Semibold", 14)).pack(anchor="w")

        # Stringa dinamica con gli intrinseci correnti
        self.var_intrinseci_testo.set(f"f={self.focale:.4g}, cx={self.cx:.4g}, cy={self.cy:.4g}")
        tk.Label(sinistra, textvariable=self.var_intrinseci_testo, fg="#666").pack(anchor="w", pady=(0, 8))

        tk.Label(
            sinistra,
            text=(
                "Inserisci le coordinate del punto 3D come X,Y,Z e premi Invio.\n"
                "Ogni punto viene proiettato e numerato; puoi vedere sia la vista 2D (piano immagine) sia la vista 3D."
            ),
            justify="left",
        ).pack(anchor="w")

        # Riga input punto
        riga = tk.Frame(sinistra)
        riga.pack(anchor="w", pady=(8, 6))
        tk.Label(riga, text="Punto 3D (X,Y,Z):").pack(side="left")
        ingresso_punto = tk.Entry(riga, textvariable=self.var_punto, width=28)
        ingresso_punto.pack(side="left", padx=(8, 0))
        ingresso_punto.bind("<Return>", self.aggiungi_punto)
        ttk.Button(riga, text="Aggiungi", command=self.aggiungi_punto).pack(side="left", padx=(8, 0))

        # Tabella dei punti
        colonne = ("#", "X", "Y", "Z", "u", "v")
        self.albero_punti = ttk.Treeview(sinistra, columns=colonne, show="headings", height=16)
        for c in colonne:
            self.albero_punti.heading(c, text=c)
            self.albero_punti.column(c, anchor="center", width=60 if c == "#" else 90)
        self.albero_punti.pack(fill="both", expand=True, pady=(10, 6))

        # Utility: esporta/importa/reset
        strumenti = tk.Frame(sinistra)
        strumenti.pack(fill="x", pady=(2, 0))
        ttk.Button(strumenti, text="Esporta txt…", command=self.esporta_txt).pack(side="left")
        ttk.Button(strumenti, text="Importa txt…", command=self.importa_txt).pack(side="left", padx=(6, 0))
        ttk.Button(strumenti, text="Reset", command=self.reset_totale).pack(side="right")

        # ------------------ COLONNA DESTRA (grafici + opzioni) ------------------
        destra = tk.Frame(frame, padx=12, pady=12)
        destra.grid(row=0, column=1, sticky="nsew")

        tk.Label(destra, text="Visualizzazione", font=("Segoe UI Semibold", 14)).pack(anchor="w")

        # Scelta vista: 2D / 3D
        opzioni_vista = tk.Frame(destra)
        opzioni_vista.pack(anchor="w", pady=(6, 2))
        ttk.Radiobutton(
            opzioni_vista, text="Vista 2D (piano immagine)", variable=self.modalita_vista, value="2D", command=self.cambia_vista
        ).pack(side="left")
        ttk.Radiobutton(
            opzioni_vista, text="Vista 3D (piano 3D)", variable=self.modalita_vista, value="3D", command=self.cambia_vista
        ).pack(side="left", padx=(12, 0))

        # Opzioni di collegamento
        opzioni_linee = tk.Frame(destra)
        opzioni_linee.pack(anchor="w", pady=(2, 4))
        ttk.Checkbutton(
            opzioni_linee, text="Collega punti in ordine", variable=self.collega_in_ordine_var,
            command=lambda: self.ridisegna_corrente(autoscale=True)
        ).pack(side="left")
        ttk.Checkbutton(
            opzioni_linee, text="Chiudi poligono", variable=self.chiudi_poligono_var,
            command=lambda: self.ridisegna_corrente(autoscale=True)
        ).pack(side="left", padx=(12, 0))
        ttk.Checkbutton(
            opzioni_linee, text="Mostra spigoli manuali", variable=self.mostra_spigoli_manuali_var,
            command=lambda: self.ridisegna_corrente(autoscale=False)
        ).pack(side="left", padx=(12, 0))

        # Pannello per collegamenti manuali
        spigoli_box = tk.LabelFrame(destra, text="Collega punti (manuale)", padx=8, pady=6)
        spigoli_box.pack(fill="x", pady=(6, 8))
        tk.Label(spigoli_box, text="Indica i due numeri separati da virgola (es. 6,2):").pack(side="left")
        ingresso_spigolo = tk.Entry(spigoli_box, textvariable=self.var_spigolo, width=10)
        ingresso_spigolo.pack(side="left", padx=(8, 0))
        ingresso_spigolo.bind("<Return>", self.aggiungi_spigolo)
        ttk.Button(spigoli_box, text="Collega", command=self.aggiungi_spigolo).pack(side="left", padx=(8, 0))
        ttk.Button(spigoli_box, text="Annulla ultimo", command=self.annulla_spigolo).pack(side="left", padx=(6, 0))
        ttk.Button(spigoli_box, text="Svuota spigoli", command=self.svuota_spigoli).pack(side="left", padx=(6, 0))

        # Contenitore per le due canvas (2D e 3D)
        contenitore_plot = tk.Frame(destra)
        contenitore_plot.pack(fill="both", expand=True)

        # ----- VISTA 2D -----
        self.figura_2d = Figure(figsize=(5, 4), dpi=100)
        self.assi_2d = self.figura_2d.add_subplot(111)
        self.assi_2d.set_xlabel("u (pixel)")
        self.assi_2d.set_ylabel("v (pixel)")
        self.assi_2d.grid(True, alpha=0.25)
        self.assi_2d.plot(self.cx, self.cy, marker="+", markersize=12, linestyle="None", label="Principal point")
        self.assi_2d.legend(loc="best")

        self.canvas_2d = FigureCanvasTkAgg(self.figura_2d, master=contenitore_plot)
        self.widget_canvas_2d = self.canvas_2d.get_tk_widget()
        self.toolbar_2d = NavigationToolbar2Tk(self.canvas_2d, destra)
        self.toolbar_2d.update()

        # ----- VISTA 3D -----
        self.figura_3d = Figure(figsize=(5, 4), dpi=100)
        self.assi_3d = self.figura_3d.add_subplot(111, projection="3d")
        self.assi_3d.set_xlabel("X")
        self.assi_3d.set_ylabel("Y")
        self.assi_3d.set_zlabel("Z")
        self.assi_3d.grid(True)
        try:
            self.assi_3d.set_box_aspect((1, 1, 1))  # cubico per prospettiva corretta
        except Exception:
            pass

        self.canvas_3d = FigureCanvasTkAgg(self.figura_3d, master=contenitore_plot)
        self.widget_canvas_3d = self.canvas_3d.get_tk_widget()
        self.toolbar_3d = NavigationToolbar2Tk(self.canvas_3d, destra)
        self.toolbar_3d.update()

        # Avvio sulla vista 2D
        self.mostra_vista_2d()

        # Barra di stato in basso
        self.etichetta_stato = tk.Label(frame, text="", anchor="w", fg="#555")
        self.etichetta_stato.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 8))

    # ------------------------------------------------------------------ #
    # LOGICA DATI: PROIEZIONE E INSERIMENTO
    # ------------------------------------------------------------------ #
    def proietta_punto(self, x: float, y: float, z: float) -> tuple[float, float]:
        """Ritorna la proiezione (u,v) del punto 3D (x,y,z) con il modello pinhole.

        Raises:
            ValueError: se z <= 0 (punto dietro il piano dell'immagine / dietro la camera).
        """
        if z <= 0:
            raise ValueError("Z deve essere > 0 (il punto deve trovarsi davanti alla camera).")
        u = self.focale * (x / z) + self.cx
        v = self.focale * (y / z) + self.cy
        return u, v

    def aggiungi_punto(self, _evento=None) -> None:
        """Parsa l'input 'X,Y,Z', calcola (u,v), aggiorna tabella e ridisegna le viste."""
        grezzo = self.var_punto.get().strip()
        parti = [p.strip().replace(",", ".") for p in grezzo.split(",")]
        if len(parti) != 3:
            messagebox.showerror("Formato non corretto", "Usa X,Y,Z (es. 0,200,2000).")
            return
        try:
            x, y, z = map(float, parti)
            assert all(map(math.isfinite, (x, y, z)))
        except Exception:
            messagebox.showerror("Valori non validi", "X, Y, Z devono essere numerici.")
            return

        # Proiezione (u,v)
        try:
            u, v = self.proietta_punto(x, y, z)
        except Exception as e:
            messagebox.showerror("Proiezione non valida", str(e))
            return

        # Aggiorna dataset e tabella
        self.punti_3d.append((x, y, z))
        self.punti_2d.append((u, v))
        indice = len(self.punti_2d)
        self.albero_punti.insert("", "end", values=(indice, f"{x:.6g}", f"{y:.6g}", f"{z:.6g}", f"{u:.4f}", f"{v:.4f}"))

        # Pulizia input e refresh
        self.var_punto.set("")
        self.etichetta_stato.configure(text=f"Aggiunto #{indice}  P=({x}, {y}, {z})  ->  p=({u:.2f}, {v:.2f})")
        self.ridisegna_corrente(autoscale=True)

    # ------------------------------------------------------------------ #
    # GESTIONE SPIGOLI MANUALI
    # ------------------------------------------------------------------ #
    def aggiungi_spigolo(self, _evento=None) -> None:
        """Aggiunge un collegamento manuale tra due indici (i,j) 1-based."""
        if len(self.punti_2d) < 2:
            messagebox.showinfo("Pochi punti", "Inserisci almeno due punti prima di collegarli.")
            return

        s = self.var_spigolo.get().strip()
        if not s:
            messagebox.showerror("Input mancante", "Indica i due numeri separati da virgola (es. 6,2).")
            return

        parti = [p.strip() for p in s.split(",")]
        if len(parti) != 2 or not all(p.isdigit() for p in parti):
            messagebox.showerror("Formato non corretto", "Usa due interi separati da virgola (es. 6,2).")
            return

        i, j = map(int, parti)
        n = len(self.punti_2d)
        if not (1 <= i <= n and 1 <= j <= n):
            messagebox.showerror("Indici non validi", f"Gli indici devono essere tra 1 e {n}.")
            return
        if i == j:
            messagebox.showerror("Indici identici", "Scegli due punti diversi.")
            return

        chiave = (min(i, j), max(i, j))  # spigolo non orientato (evita duplicati)
        if chiave in self.spigoli_manuali:
            messagebox.showinfo("Già presente", f"Lo spigolo {i}-{j} è già stato aggiunto.")
            return

        self.spigoli_manuali.append(chiave)
        self.var_spigolo.set("")
        self.etichetta_stato.configure(text=f"Collegati i punti {i} e {j}.")
        self.ridisegna_corrente(autoscale=False)

    def annulla_spigolo(self) -> None:
        """Elimina l'ultimo spigolo manuale inserito (se presente)."""
        if not self.spigoli_manuali:
            messagebox.showinfo("Nessuno spigolo", "Non ci sono spigoli manuali da annullare.")
            return
        ultimo = self.spigoli_manuali.pop()
        self.etichetta_stato.configure(text=f"Rimosso ultimo spigolo {ultimo[0]}-{ultimo[1]}.")
        self.ridisegna_corrente(autoscale=False)

    def svuota_spigoli(self) -> None:
        """Cancella tutti gli spigoli manuali."""
        if not self.spigoli_manuali:
            return
        self.spigoli_manuali.clear()
        self.etichetta_stato.configure(text="Spigoli manuali svuotati.")
        self.ridisegna_corrente(autoscale=False)

    # ------------------------------------------------------------------ #
    # RENDERING E UTILITY GRAFICHE
    # ------------------------------------------------------------------ #
    @staticmethod
    def coord_polilinea(coordinate: list, chiudi: bool) -> list:
        """Ritorna una copia della lista `coordinate`, eventualmente chiusa (append del primo).

        Args:
            coordinate: lista di punti 2D o 3D (tuples).
            chiudi: se True e ci sono ≥3 punti, aggiunge coordinate[0] in coda.

        Returns:
            list: lista di coordinate pronta da plottare come polilinea.
        """
        if not coordinate:
            return []
        return list(coordinate) + [coordinate[0]] if (chiudi and len(coordinate) >= 3) else list(coordinate)

    def ridisegna_corrente(self, autoscale: bool = False) -> None:
        """Redraw dispatcher: chiama ridisegna_2d o ridisegna_3d in base alla vista selezionata."""
        if self.modalita_vista.get() == "2D":
            self.ridisegna_2d(autoscale=autoscale)
        else:
            self.ridisegna_3d(autoscale=autoscale)

    def ridisegna_2d(self, autoscale: bool = False) -> None:
        """Aggiorna completamente la vista 2D (assi, punti, etichette, collegamenti)."""
        assi = self.assi_2d
        assi.clear()
        assi.set_xlabel("u (pixel)")
        assi.set_ylabel("v (pixel)")
        assi.grid(True, alpha=0.25)

        # Punto principale
        assi.plot(self.cx, self.cy, marker="+", markersize=12, linestyle="None", label="Principal point")

        # Punti (u,v) e numerazione
        if self.punti_2d:
            us, vs = zip(*self.punti_2d)
            assi.plot(us, vs, "o", linestyle="None", zorder=3)
            for k, (u, v) in enumerate(self.punti_2d, start=1):
                assi.annotate(str(k), (u, v), textcoords="offset points", xytext=(4, 4),
                              fontsize=9, color="#444", zorder=4)

        # Collegamenti automatici
        if self.collega_in_ordine_var.get() and len(self.punti_2d) >= 2:
            pts = self.coord_polilinea(self.punti_2d, self.chiudi_poligono_var.get())
            xs, ys = zip(*pts)
            assi.plot(xs, ys, "-", linewidth=1.8, zorder=2)

        # Spigoli manuali (linea tratteggiata)
        if self.mostra_spigoli_manuali_var.get():
            for (i, j) in self.spigoli_manuali:
                (u1, v1) = self.punti_2d[i - 1]
                (u2, v2) = self.punti_2d[j - 1]
                assi.plot([u1, u2], [v1, v2], linestyle="--", linewidth=1.8, zorder=2)

        assi.legend(loc="best")
        if autoscale:
            self.autoscale_2d(assi)
        self.canvas_2d.draw_idle()

    @staticmethod
    def autoscale_2d(assi, rapporto_margine: float = 0.10) -> None:
        """Autoscale per la vista 2D: adatta i limiti con un margine percentuale."""
        assi.relim()
        assi.autoscale_view()
        x0, x1 = assi.get_xlim()
        y0, y1 = assi.get_ylim()
        dx = (x1 - x0) or 1.0
        dy = (y1 - y0) or 1.0
        mx = dx * rapporto_margine
        my = dy * rapporto_margine
        assi.set_xlim(x0 - mx, x1 + mx)
        assi.set_ylim(y0 - my, y1 + my)

    def ridisegna_3d(self, autoscale: bool = False) -> None:
        """Aggiorna completamente la vista 3D (assi, punti, etichette, collegamenti)."""
        assi = self.assi_3d
        assi.clear()
        assi.set_xlabel("X")
        assi.set_ylabel("Y")
        assi.set_zlabel("Z")
        assi.grid(True)

        # Punti 3D e numerazione
        if self.punti_3d:
            xs, ys, zs = zip(*self.punti_3d)
            assi.scatter(xs, ys, zs, s=30, depthshade=True)
            for k, (x, y, z) in enumerate(self.punti_3d, start=1):
                assi.text(x, y, z, str(k), fontsize=9, color="#333")

        # Collegamenti automatici
        if self.collega_in_ordine_var.get() and len(self.punti_3d) >= 2:
            pts = self.coord_polilinea(self.punti_3d, self.chiudi_poligono_var.get())
            xs, ys, zs = zip(*pts)
            assi.plot(xs, ys, zs, linewidth=1.8)

        # Spigoli manuali (tratteggiati)
        if self.mostra_spigoli_manuali_var.get():
            for (i, j) in self.spigoli_manuali:
                (x1, y1, z1) = self.punti_3d[i - 1]
                (x2, y2, z2) = self.punti_3d[j - 1]
                assi.plot([x1, x2], [y1, y2], [z1, z2], linestyle="--", linewidth=1.8)

        if autoscale:
            self.autoscale_3d(assi, self.punti_3d)
        try:
            assi.set_box_aspect((1, 1, 1))
        except Exception:
            pass

        self.canvas_3d.draw_idle()

    @staticmethod
    def autoscale_3d(assi, punti_3d: list[tuple[float, float, float]], rapporto_margine: float = 0.10) -> None:
        """Autoscale isotropo per il 3D, basato esclusivamente sui `punti_3d`."""
        if not punti_3d:
            assi.set_xlim(-1, 1)
            assi.set_ylim(-1, 1)
            assi.set_zlim(0, 2)
            return

        xs, ys, zs = zip(*punti_3d)
        min_x, min_y, min_z = min(xs), min(ys), min(zs)
        max_x, max_y, max_z = max(xs), max(ys), max(zs)
        range_x, range_y, range_z = max_x - min_x, max_y - min_y, max_z - min_z
        max_range = max(range_x, range_y, range_z) or 1.0

        cx = (max_x + min_x) / 2.0
        cy = (max_y + min_y) / 2.0
        cz = (max_z + min_z) / 2.0

        half = max_range / 2.0
        margine = max_range * rapporto_margine

        assi.set_xlim(cx - half - margine, cx + half + margine)
        assi.set_ylim(cy - half - margine, cy + half + margine)
        assi.set_zlim(cz - half - margine, cz + half + margine)

    # ------------------------------------------------------------------ #
    # SWITCH VISTE E RESET
    # ------------------------------------------------------------------ #
    def mostra_vista_2d(self) -> None:
        """Mostra la canvas 2D (nascondendo la 3D) e ridisegna con autoscale."""
        try:
            self.widget_canvas_3d.pack_forget()
            self.toolbar_3d.pack_forget()
        except Exception:
            pass
        self.widget_canvas_2d.pack(fill="both", expand=True)
        self.toolbar_2d.pack(side="bottom", fill="x")
        self.ridisegna_2d(autoscale=True)

    def mostra_vista_3d(self) -> None:
        """Mostra la canvas 3D (nascondendo la 2D) e ridisegna con autoscale."""
        try:
            self.widget_canvas_2d.pack_forget()
            self.toolbar_2d.pack_forget()
        except Exception:
            pass
        self.widget_canvas_3d.pack(fill="both", expand=True)
        self.toolbar_3d.pack(side="bottom", fill="x")
        self.ridisegna_3d(autoscale=True)

    def cambia_vista(self) -> None:
        """Callback dei radio button: commuta tra vista 2D e 3D."""
        if self.modalita_vista.get() == "2D":
            self.mostra_vista_2d()
        else:
            self.mostra_vista_3d()

    def reset_totale(self) -> None:
        """Pulisce completamente i dati (punti e spigoli) e svuota la tabella."""
        self.punti_3d.clear()
        self.punti_2d.clear()
        self.spigoli_manuali.clear()
        for item in self.albero_punti.get_children():
            self.albero_punti.delete(item)
        self.ridisegna_corrente(autoscale=True)
        self.etichetta_stato.configure(text="")

    # ------------------------------------------------------------------ #
    # IMPORT / EXPORT
    # ------------------------------------------------------------------ #
    def esporta_txt(self) -> None:
        """Esporta su .txt: intrinseci, punti (X,Y,Z,u,v) e spigoli manuali con formato leggibile."""
        if not self.punti_3d:
            messagebox.showinfo("Nessun dato", "Non ci sono punti da esportare.")
            return

        percorso = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("File di testo", "*.txt"), ("Tutti i file", "*.*")],
            title="Esporta dati come file .txt",
        )
        if not percorso:
            return

        try:
            with open(percorso, "w", encoding="utf-8") as f:
                f.write("==================== COORDCODE — ESPORTAZIONE DATI ====================\n")
                f.write("Descrizione: punti 3D, proiezioni (u,v) sul piano immagine e collegamenti definiti dall’utente.\n")
                f.write("Nota: i punti sono elencati nell’ordine di inserimento; le coordinate u,v sono in pixel.\n\n")

                f.write("[Camera]\n")
                f.write(f"  f  = {self.focale:.6g}        # focale in pixel\n")
                f.write(f"  cx = {self.cx:.6g}        # coordinata u del punto principale\n")
                f.write(f"  cy = {self.cy:.6g}        # coordinata v del punto principale\n\n")

                f.write("[Punti]\n")
                f.write("  # indice | X | Y | Z || u | v\n")
                for i, ((x, y, z), (u, v)) in enumerate(zip(self.punti_3d, self.punti_2d), start=1):
                    # Larghezza prima della precisione (FIX al formato)
                    f.write(f"  {i:>2})  X={x:<10.6g} Y={y:<10.6g} Z={z:<10.6g}  ==>  u={u:<10.4f} v={v:.4f}\n")

                f.write("\n[SpigoliManuali]\n")
                f.write("  # elenco di coppie (i, j) che collegano i punti con indici i e j\n")
                if self.spigoli_manuali:
                    for (i, j) in self.spigoli_manuali:
                        f.write(f"  ({i}, {j})\n")
                else:
                    f.write("  (nessuno)\n")

                f.write("=========================== FINE ESPORTAZIONE =========================\n")

            messagebox.showinfo("Esportazione completata", f"Dati salvati in:\n{percorso}")
        except Exception as e:
            messagebox.showerror("Errore di scrittura", str(e))

    def importa_txt(self) -> None:
        """Importa da .txt: riconosce le sezioni [Camera], [Punti], [SpigoliManuali] e ricarica tutto."""
        percorso = filedialog.askopenfilename(
            filetypes=[("File di testo", "*.txt"), ("Tutti i file", "*.*")],
            title="Importa dati da file .txt",
        )
        if not percorso:
            return

        try:
            nuovi_punti_3d: list[tuple[float, float, float]] = []
            nuovi_punti_2d: list[tuple[float, float]] = []
            nuovi_spigoli: list[tuple[int, int]] = []

            nuova_f, nuovo_cx, nuovo_cy = self.focale, self.cx, self.cy
            sezione = None

            with open(percorso, "r", encoding="utf-8") as f:
                for riga in f:
                    s = riga.strip()
                    if not s or s.startswith("#") or s.startswith("="):
                        continue
                    if s.startswith("[") and s.endswith("]"):
                        sezione = s[1:-1]  # nome della sezione
                        continue

                    if sezione == "Camera":
                        # Righe del tipo: "cx = 320.0   # commento"
                        if "=" in s:
                            chiave, valore = s.split("=", 1)
                            chiave = chiave.strip().lower()
                            valore = valore.split("#")[0].strip().replace(",", ".")
                            try:
                                if chiave == "f":
                                    nuova_f = float(valore)
                                elif chiave == "cx":
                                    nuovo_cx = float(valore)
                                elif chiave == "cy":
                                    nuovo_cy = float(valore)
                            except Exception:
                                pass

                    elif sezione == "Punti":
                        # Righe del tipo: "1)  X=...  Y=...  Z=...  ==>  u=...  v=..."
                        if "X=" in s and "Y=" in s and "Z=" in s:
                            try:
                                token = s.replace(")", "").split()
                                mappa = {}
                                for t in token:
                                    if "=" in t:
                                        k, v = t.split("=", 1)
                                        mappa[k.strip().lower()] = v.strip().replace(",", ".")
                                x = float(mappa["x"]); y = float(mappa["y"]); z = float(mappa["z"])
                                u = float(mappa["u"]); v = float(mappa["v"])
                                nuovi_punti_3d.append((x, y, z))
                                nuovi_punti_2d.append((u, v))
                            except Exception:
                                continue
                        else:
                            # Formato alternativo tollerato: "1 | X | Y | Z | u | v"
                            campi = [c.strip() for c in s.replace(";", "|").split("|")]
                            if len(campi) >= 6 and campi[0][0].isdigit():
                                try:
                                    _, x, y, z, u, v = campi[:6]
                                    x = float(x); y = float(y); z = float(z); u = float(u); v = float(v)
                                    nuovi_punti_3d.append((x, y, z)); nuovi_punti_2d.append((u, v))
                                except Exception:
                                    pass

                    elif sezione == "SpigoliManuali":
                        # Righe tipo "(i, j)" o "i-j" o "i,j"
                        s2 = s.replace("(", "").replace(")", "").replace(" ", "").replace("-", ",")
                        parti = s2.split(",")
                        if len(parti) == 2 and all(p.isdigit() for p in parti):
                            i, j = map(int, parti)
                            if i != j:
                                chiave = (min(i, j), max(i, j))
                                if chiave not in nuovi_spigoli:
                                    nuovi_spigoli.append(chiave)

            # Validazione minima
            if not nuovi_punti_3d or not nuovi_punti_2d or len(nuovi_punti_3d) != len(nuovi_punti_2d):
                messagebox.showerror("Importazione fallita", "Il file non contiene una sezione [Punti] valida.")
                return

            # Applica i nuovi dati
            self.punti_3d = nuovi_punti_3d
            self.punti_2d = nuovi_punti_2d
            self.spigoli_manuali = nuovi_spigoli

            # Aggiorna intrinseci se presenti
            self.focale = nuova_f
            self.cx = nuovo_cx
            self.cy = nuovo_cy
            self.var_intrinseci_testo.set(f"f={self.focale:.4g}, cx={self.cx:.4g}, cy={self.cy:.4g}")

            # Ricostruzione tabella
            for item in self.albero_punti.get_children():
                self.albero_punti.delete(item)
            for i, ((x, y, z), (u, v)) in enumerate(zip(self.punti_3d, self.punti_2d), start=1):
                self.albero_punti.insert("", "end", values=(i, f"{x:.6g}", f"{y:.6g}", f"{z:.6g}", f"{u:.4f}", f"{v:.4f}"))

            self.etichetta_stato.configure(text=f"Importate {len(self.punti_3d)} righe dal file selezionato.")
            self.ridisegna_corrente(autoscale=True)

        except Exception as e:
            messagebox.showerror("Errore di importazione", str(e))

# =============================================================================
# AVVIO APPLICAZIONE
# =============================================================================
def main() -> None:
    """Entry point: crea la finestra Tk e lancia l'applicazione."""
    radice = tk.Tk()
    app = ApplicazioneCoordCode(radice)
    radice.mainloop()

if __name__ == "__main__":
    main()