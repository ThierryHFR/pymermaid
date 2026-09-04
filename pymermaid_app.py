#!/usr/bin/env python3
"""Local graphical application for generating Mermaid SVG and PDF files."""

from __future__ import annotations

from io import BytesIO
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# Also supports launching with the system Python: python3 pymermaid_app.py
# Allows the system Python to find CairoSVG in the project's virtual environment.
PROJECT_DIR = Path(__file__).resolve().parent
for site_packages in (PROJECT_DIR / ".venv" / "lib").glob("python*/site-packages"):
    if str(site_packages) not in sys.path:
        sys.path.insert(0, str(site_packages))

if sys.platform == "win32":
    # CairoSVG uses cairocffi, which loads Cairo dynamically. In a PyInstaller
    # bundle, point cairocffi to the extracted application directory.
    bundle_dir = Path(getattr(sys, "_MEIPASS", PROJECT_DIR))
    os.environ.setdefault("CAIROCFFI_DLL_DIRECTORIES", str(bundle_dir))
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(bundle_dir))

from mermaid_renderer import MermaidRenderer

TEXTS = {
    "fr": {"file": "Fichier", "open": "Ouvrir…", "save": "Enregistrer…", "quit": "Quitter", "export": "Exporter", "svg": "Exporter en SVG…", "pdf": "Exporter en PDF…", "about": "À propos", "license": "Licence GPL v3", "readme": "Aperçu du README", "language": "Langue", "code": "Code Mermaid", "preview": "Prévisualisation", "ready": "Prêt", "updated": "Prévisualisation mise à jour", "done": "Export terminé", "created": "Le fichier a été créé :\n", "error": "Erreur", "missing": "Bibliothèque absente", "install": "Installe CairoSVG avec :\npython3 -m pip install -r requirements.txt"},
    "en": {"file": "File", "open": "Open…", "save": "Save…", "quit": "Quit", "export": "Export", "svg": "Export SVG…", "pdf": "Export PDF…", "about": "About", "license": "GPL v3 License", "readme": "README Preview", "language": "Language", "code": "Mermaid Code", "preview": "Preview", "ready": "Ready", "updated": "Preview updated", "done": "Export complete", "created": "File created:\n", "error": "Error", "missing": "Missing library", "install": "Install CairoSVG with:\npython3 -m pip install -r requirements.txt"},
    "de": {"file": "Datei", "open": "Öffnen…", "save": "Speichern…", "quit": "Beenden", "export": "Exportieren", "svg": "SVG exportieren…", "pdf": "PDF exportieren…", "about": "Über", "license": "GPL-v3-Lizenz", "readme": "README-Vorschau", "language": "Sprache", "code": "Mermaid-Code", "preview": "Vorschau", "ready": "Bereit", "updated": "Vorschau aktualisiert", "done": "Export abgeschlossen", "created": "Datei erstellt:\n", "error": "Fehler", "missing": "Bibliothek fehlt", "install": "CairoSVG installieren mit:\npython3 -m pip install -r requirements.txt"},
    "es": {"file": "Archivo", "open": "Abrir…", "save": "Guardar…", "quit": "Salir", "export": "Exportar", "svg": "Exportar SVG…", "pdf": "Exportar PDF…", "about": "Acerca de", "license": "Licencia GPL v3", "readme": "Vista previa del README", "language": "Idioma", "code": "Código Mermaid", "preview": "Vista previa", "ready": "Listo", "updated": "Vista previa actualizada", "done": "Exportación terminada", "created": "Archivo creado:\n", "error": "Error", "missing": "Falta la biblioteca", "install": "Instala CairoSVG con:\npython3 -m pip install -r requirements.txt"},
    "it": {"file": "File", "open": "Apri…", "save": "Salva…", "quit": "Esci", "export": "Esporta", "svg": "Esporta SVG…", "pdf": "Esporta PDF…", "about": "Informazioni", "license": "Licenza GPL v3", "readme": "Anteprima README", "language": "Lingua", "code": "Codice Mermaid", "preview": "Anteprima", "ready": "Pronto", "updated": "Anteprima aggiornata", "done": "Esportazione completata", "created": "File creato:\n", "error": "Errore", "missing": "Libreria mancante", "install": "Installa CairoSVG con:\npython3 -m pip install -r requirements.txt"},
}


DEFAULT_SOURCE = """flowchart TD
    A[Start] --> B{Choice?}
    B -->|Yes| C[Validate request]
    B -->|No| D[Review information]
    D --> B
    C --> E[End]
"""


class MermaidApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PyMermaid")
        self.geometry("900x650")
        self.minsize(700, 450)
        self.renderer = MermaidRenderer()
        self.lang = "fr"
        self.preview_job: str | None = None
        self.preview_image: tk.PhotoImage | None = None
        self.preview_bitmap = None
        self.create_menu()
        self._build_ui()
        self.schedule_preview()

    def create_menu(self) -> None:
        t = TEXTS[self.lang]
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label=t["open"], command=self.open_source, accelerator="Ctrl+O")
        file_menu.add_command(label=t["save"], command=self.save_source, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label=t["quit"], command=self.destroy, accelerator="Ctrl+Q")
        menubar.add_cascade(label=t["file"], menu=file_menu)

        export_menu = tk.Menu(menubar, tearoff=False)
        export_menu.add_command(label=t["svg"], command=self.export_svg)
        export_menu.add_command(label=t["pdf"], command=self.export_pdf)
        menubar.add_cascade(label=t["export"], menu=export_menu)

        about_menu = tk.Menu(menubar, tearoff=False)
        about_menu.add_command(label=t["license"], command=self.show_license)
        about_menu.add_command(label=t["readme"], command=self.show_readme)
        menubar.add_cascade(label=t["about"], menu=about_menu)

        language_menu = tk.Menu(menubar, tearoff=False)
        for code, name in (("fr", "Français"), ("en", "English"), ("de", "Deutsch"), ("es", "Español"), ("it", "Italiano")):
            language_menu.add_command(label=name, command=lambda code=code: self.set_language(code))
        menubar.add_cascade(label=t["language"], menu=language_menu)
        self.config(menu=menubar)
        self.bind_all("<Control-o>", lambda _event: self.open_source())
        self.bind_all("<Control-s>", lambda _event: self.save_source())
        self.bind_all("<Control-q>", lambda _event: self.destroy())

    def set_language(self, language: str) -> None:
        self.lang = language if language in TEXTS else "fr"
        self.create_menu()
        self.editor_label.config(text=TEXTS[self.lang]["code"])
        self.preview_label.config(text=TEXTS[self.lang]["preview"])
        self.status.config(text=TEXTS[self.lang]["ready"])

    def show_license(self) -> None:
        messagebox.showinfo("GPL v3 License", "PyMermaid is distributed under the GNU GPL v3 license.\n\nFull text: https://www.gnu.org/licenses/gpl-3.0.html")

    def show_readme(self) -> None:
        try:
            content = (PROJECT_DIR / "README.md").read_text(encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("README not found", str(exc))
            return
        window = tk.Toplevel(self)
        window.title("README — PyMermaid")
        window.geometry("760x560")
        text = tk.Text(window, wrap="word", font=("Arial", 11), padx=14, pady=14)
        scroll = ttk.Scrollbar(window, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        text.insert("1.0", content)
        text.configure(state="disabled")

    def _build_ui(self) -> None:
        panes = tk.PanedWindow(self, orient="horizontal", sashwidth=7, sashrelief="raised", bg="#cbd5e1", bd=0)
        panes.pack(fill="both", expand=True, padx=10, pady=(0, 4))
        panes.bind("<B1-Motion>", self.limit_editor_width)
        self.panes = panes

        editor_frame = ttk.Frame(panes, padding=(0, 0, 8, 0))
        preview_frame = ttk.Frame(panes, padding=(8, 0, 0, 0))
        panes.add(editor_frame, minsize=180, stretch="always")
        panes.add(preview_frame, minsize=300, stretch="always")

        self.editor_label = ttk.Label(editor_frame, text=TEXTS[self.lang]["code"], padding=(0, 0, 0, 4))
        self.editor_label.pack(anchor="w")
        editor_area = ttk.Frame(editor_frame)
        editor_area.pack(fill="both", expand=True)
        editor_area.columnconfigure(0, weight=1)
        editor_area.rowconfigure(0, weight=1)
        self.editor = tk.Text(
            editor_area,
            wrap="none",
            undo=True,
            font=("DejaVu Sans Mono", 12),
            padx=10,
            pady=10,
            xscrollcommand=lambda *args: horizontal_scroll.set(*args),
            yscrollcommand=lambda *args: vertical_scroll.set(*args),
        )
        vertical_scroll = ttk.Scrollbar(editor_area, orient="vertical", command=self.editor.yview)
        horizontal_scroll = ttk.Scrollbar(editor_area, orient="horizontal", command=self.editor.xview)
        self.editor.grid(row=0, column=0, sticky="nsew")
        vertical_scroll.grid(row=0, column=1, sticky="ns")
        horizontal_scroll.grid(row=1, column=0, sticky="ew")
        self.editor.bind("<<Modified>>", self.on_editor_modified)

        self.preview_label = ttk.Label(preview_frame, text=TEXTS[self.lang]["preview"], padding=(0, 0, 0, 4))
        self.preview_label.pack(anchor="w")
        preview_border = ttk.Frame(preview_frame, relief="sunken", borderwidth=1)
        preview_border.pack(fill="both", expand=True)
        self.preview = tk.Label(preview_border, text="Rendering preview…", bg="white", anchor="center")
        self.preview.pack(fill="both", expand=True)
        self.preview.bind("<Configure>", self.resize_preview)
        self.editor.insert("1.0", DEFAULT_SOURCE)
        self.status = ttk.Label(self, text=TEXTS[self.lang]["ready"], padding=10, relief="sunken", anchor="w")
        self.status.pack(fill="x", padx=10, pady=(0, 10))
        self.after_idle(lambda: self.panes.sash_place(0, 300, 0))

    def limit_editor_width(self, event) -> None:
        """Prevent the editor handle from exceeding 300 px."""
        x = max(180, min(300, event.x))
        self.panes.sash_place(0, x, 0)

    def source(self) -> str:
        return self.editor.get("1.0", "end-1c")

    def on_editor_modified(self, _event=None) -> None:
        self.editor.edit_modified(False)
        self.schedule_preview()

    def schedule_preview(self) -> None:
        if self.preview_job is not None:
            self.after_cancel(self.preview_job)
        self.preview_job = self.after(350, self.update_preview)

    def update_preview(self) -> None:
        self.preview_job = None
        try:
            import cairosvg
            png = cairosvg.svg2png(
                bytestring=self.renderer.render(self.source()).encode("utf-8"),
                output_width=1800,
            )
            from PIL import Image
            self.preview_bitmap = Image.open(BytesIO(png)).convert("RGBA")
            # The pane may still be one pixel wide during the first render.
            self.after_idle(self.resize_preview)
            self.status.config(text=TEXTS[self.lang]["updated"])
        except Exception as exc:
            self.preview_image = None
            self.preview.configure(image="", text=f"Rendering error:\n{exc}\nPython: {sys.executable}", fg="#b91c1c")

    def resize_preview(self, _event=None) -> None:
        if self.preview_bitmap is None:
            return
        from PIL import Image
        from PIL import ImageTk
        self.preview.update_idletasks()
        available_width = max(100, self.preview.winfo_width() - 20)
        available_height = max(100, self.preview.winfo_height() - 20)
        source_width, source_height = self.preview_bitmap.size
        ratio = min(available_width / source_width, available_height / source_height)
        size = (max(1, int(source_width * ratio)), max(1, int(source_height * ratio)))
        bitmap = self.preview_bitmap.resize(size, Image.Resampling.LANCZOS)
        self.preview_image = ImageTk.PhotoImage(bitmap, master=self)
        self.preview.configure(image=self.preview_image, text="", fg="#0f172a")

    def open_source(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Mermaid", "*.mmd *.mermaid"), ("All files", "*.*")])
        if not path: return
        try:
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", Path(path).read_text(encoding="utf-8"))
            self.editor.edit_modified(False)
            self.schedule_preview()
            self.status.config(text=f"Ouvert : {path}")
        except Exception as exc:
            messagebox.showerror("Unable to open file", str(exc))

    def save_source(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".mmd", filetypes=[("Mermaid", "*.mmd")])
        if path:
            Path(path).write_text(self.source(), encoding="utf-8")
            self.status.config(text=f"Saved: {path}")

    def export_svg(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".svg", filetypes=[("SVG", "*.svg")])
        if not path: return
        try:
            self.renderer.render_text_to_file(self.source(), path)
            self.status.config(text=f"SVG generated: {path}")
            messagebox.showinfo("Export complete", f"SVG file created:\n{path}")
        except Exception as exc:
            messagebox.showerror(TEXTS[self.lang]["error"], str(exc))

    def export_pdf(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not path: return
        try:
            self.renderer.render_pdf(self.source(), path)
            self.status.config(text=f"PDF generated: {path}")
            messagebox.showinfo("Export complete", f"PDF file created:\n{path}")
        except Exception as exc:
            messagebox.showerror("PDF export failed", str(exc))


if __name__ == "__main__":
    MermaidApp().mainloop()
