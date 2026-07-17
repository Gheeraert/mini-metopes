"""Petite interface Tkinter d'edition des metadonnees associees a un DOCX."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .metadata_controller import (
    MetadataEditorState, add_affiliation, add_contributor, load_metadata_editor_state,
    is_metadata_dirty, next_identifier, remove_affiliation, remove_contributor, save_metadata_editor_state,
    update_affiliation, update_contributor, validate_metadata_editor_state,
)
from mini_metopes.metadata import Affiliation, Contributor


def run_metadata_editor(docx_path: Path | None = None, metadata_path: Path | None = None) -> int:
    """Ouvrir explicitement l'editeur; aucun Tkinter n'est lance a l'import."""
    state: MetadataEditorState | None = None
    if docx_path is not None:
        state = load_metadata_editor_state(docx_path, metadata_path)
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.withdraw()
    if docx_path is None:
        selected = filedialog.askopenfilename(parent=root, filetypes=[("Documents Word", "*.docx *.DOCX")])
        if not selected:
            root.destroy()
            return 0
        docx_path = Path(selected)
    if state is None:
        state = load_metadata_editor_state(docx_path, metadata_path)
    root.deiconify()
    root.title("Mini-Metopes — Metadonnees")
    root.minsize(760, 560)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(1, weight=1)
    document = ttk.LabelFrame(root, text="Document", padding=8)
    document.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
    ttk.Label(document, text=f"DOCX : {state.docx_path}").grid(sticky="w")
    ttk.Label(document, text=f"JSON : {state.metadata_path}").grid(sticky="w")
    diagnostics_tree = ttk.Treeview(document, columns=("severity", "path", "message"), show="headings", height=4)
    diagnostics_tree.heading("severity", text="Niveau")
    diagnostics_tree.heading("path", text="Emplacement")
    diagnostics_tree.heading("message", text="Message")
    diagnostics_tree.grid(sticky="ew", pady=(6, 0))
    fields = ttk.LabelFrame(root, text="Metadonnees generales", padding=8)
    fields.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
    fields.columnconfigure(1, weight=1)
    values = {name: tk.StringVar(value=getattr(state.metadata, name) or "") for name in ("title", "subtitle", "language", "document_type")}
    for row, (label, name) in enumerate((("Titre", "title"), ("Sous-titre", "subtitle"), ("Langue", "language"), ("Type", "document_type"))):
        ttk.Label(fields, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Entry(fields, textvariable=values[name]).grid(row=row, column=1, sticky="ew", pady=2)
    ttk.Label(fields, text="Resume").grid(row=4, column=0, sticky="nw")
    abstract = tk.Text(fields, height=5, width=60)
    abstract.insert("1.0", state.metadata.abstract or "")
    abstract.grid(row=4, column=1, sticky="nsew", pady=2)
    ttk.Label(fields, text="Mots-cles (un par ligne)").grid(row=5, column=0, sticky="nw")
    keywords = tk.Text(fields, height=4, width=60)
    keywords.insert("1.0", "\n".join(state.metadata.keywords))
    keywords.grid(row=5, column=1, sticky="nsew", pady=2)
    initializing = True

    def mark_dirty(*_args: object) -> None:
        nonlocal state
        if not initializing:
            state = replace(state, dirty=True)

    for value in values.values():
        value.trace_add("write", mark_dirty)
    abstract.bind("<<Modified>>", lambda _event: (mark_dirty(), abstract.edit_modified(False)))
    keywords.bind("<<Modified>>", lambda _event: (mark_dirty(), keywords.edit_modified(False)))
    people = ttk.Frame(root, padding=8)
    people.grid(row=2, column=0, sticky="nsew", padx=10, pady=4)
    people.columnconfigure(0, weight=1)
    people.columnconfigure(1, weight=1)
    contributor_frame = ttk.LabelFrame(people, text="Contributeurs", padding=5)
    contributor_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
    affiliation_frame = ttk.LabelFrame(people, text="Affiliations", padding=5)
    affiliation_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
    contributor_tree = ttk.Treeview(contributor_frame, columns=("role", "name", "orcid", "affiliations"), show="tree headings", height=6)
    contributor_tree.heading("#0", text="Identifiant")
    contributor_tree.heading("role", text="Rôle")
    contributor_tree.heading("name", text="Nom")
    contributor_tree.heading("orcid", text="ORCID")
    contributor_tree.heading("affiliations", text="Affiliations")
    contributor_tree.grid(row=0, column=0, sticky="nsew")
    affiliation_tree = ttk.Treeview(affiliation_frame, columns=("name", "unit", "city", "country", "ror"), show="tree headings", height=6)
    affiliation_tree.heading("#0", text="Identifiant")
    affiliation_tree.heading("name", text="Institution")
    affiliation_tree.heading("unit", text="Unité")
    affiliation_tree.heading("city", text="Ville")
    affiliation_tree.heading("country", text="Pays")
    affiliation_tree.heading("ror", text="ROR")
    affiliation_tree.grid(row=0, column=0, sticky="nsew")
    actions = ttk.Frame(root, padding=10)
    actions.grid(row=3, column=0, sticky="ew")

    def collect() -> MetadataEditorState:
        metadata = replace(state.metadata, title=values["title"].get(), subtitle=values["subtitle"].get() or None,
            language=values["language"].get(), document_type=values["document_type"].get(),
            abstract=abstract.get("1.0", "end-1c") or None,
            keywords=tuple(line for line in keywords.get("1.0", "end-1c").splitlines() if line))
        return replace(state, metadata=metadata, dirty=is_metadata_dirty(state.saved_metadata, metadata))

    def refresh_diagnostics() -> None:
        diagnostics_tree.delete(*diagnostics_tree.get_children())
        if state.loaded_from_invalid_json:
            diagnostics_tree.insert("", "end", values=("ERROR", "metadata", "JSON existant invalide ; valeurs de secours affichees"))
        for issue in state.issues:
            diagnostics_tree.insert("", "end", values=(issue.severity.upper(), issue.path or "", f"[{issue.code}] {issue.message}"))

    def refresh_trees() -> None:
        refresh_diagnostics()
        contributor_tree.delete(*contributor_tree.get_children())
        for contributor in state.metadata.contributors:
            name = contributor.literal_name or " ".join(part for part in (contributor.given_name, contributor.family_name) if part)
            contributor_tree.insert("", "end", iid=contributor.contributor_id, text=contributor.contributor_id,
                                    values=(contributor.role, name, contributor.orcid or "", ", ".join(contributor.affiliation_ids)))
        affiliation_tree.delete(*affiliation_tree.get_children())
        for affiliation in state.metadata.affiliations:
            affiliation_tree.insert("", "end", iid=affiliation.affiliation_id, text=affiliation.affiliation_id,
                                    values=(affiliation.name, affiliation.unit or "", affiliation.city or "", affiliation.country or "", affiliation.ror or ""))

    def contributor_dialog(current: Contributor | None = None) -> Contributor | None:
        dialog = tk.Toplevel(root)
        dialog.title("Contributeur")
        values = {name: tk.StringVar(value=getattr(current, name) or "") for name in ("contributor_id", "role", "given_name", "family_name", "literal_name", "orcid")}
        if current is None:
            values["contributor_id"].set(next_identifier("person", tuple(item.contributor_id for item in state.metadata.contributors)))
            values["role"].set("author")
        for row, (label, name) in enumerate((("Identifiant", "contributor_id"), ("Rôle", "role"), ("Prénom", "given_name"), ("Nom", "family_name"), ("Nom littéral", "literal_name"), ("ORCID", "orcid"))):
            ttk.Label(dialog, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=2)
            ttk.Entry(dialog, textvariable=values[name], width=36).grid(row=row, column=1, padx=6, pady=2)
        affiliations = tk.StringVar(value=", ".join(current.affiliation_ids) if current else "")
        ttk.Label(dialog, text="Affiliations (IDs, virgules)").grid(row=6, column=0, sticky="w", padx=6, pady=2)
        ttk.Entry(dialog, textvariable=affiliations, width=36).grid(row=6, column=1, padx=6, pady=2)
        result: list[Contributor | None] = [None]
        def accept() -> None:
            result[0] = Contributor(values["contributor_id"].get(), values["role"].get(), values["given_name"].get() or None, values["family_name"].get() or None, values["literal_name"].get() or None, values["orcid"].get() or None, tuple(value.strip() for value in affiliations.get().split(",") if value.strip()))
            dialog.destroy()
        ttk.Button(dialog, text="Valider", command=accept).grid(row=7, column=0, padx=6, pady=6)
        ttk.Button(dialog, text="Annuler", command=dialog.destroy).grid(row=7, column=1, padx=6, pady=6)
        dialog.transient(root); dialog.grab_set(); root.wait_window(dialog)
        return result[0]

    def affiliation_dialog(current: Affiliation | None = None) -> Affiliation | None:
        dialog = tk.Toplevel(root); dialog.title("Affiliation")
        values = {name: tk.StringVar(value=getattr(current, name) or "") for name in ("affiliation_id", "name", "unit", "city", "country", "ror")}
        if current is None:
            values["affiliation_id"].set(next_identifier("affiliation", tuple(item.affiliation_id for item in state.metadata.affiliations)))
        for row, (label, name) in enumerate((("Identifiant", "affiliation_id"), ("Institution", "name"), ("Unité", "unit"), ("Ville", "city"), ("Pays", "country"), ("ROR", "ror"))):
            ttk.Label(dialog, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=2)
            ttk.Entry(dialog, textvariable=values[name], width=36).grid(row=row, column=1, padx=6, pady=2)
        result: list[Affiliation | None] = [None]
        def accept() -> None:
            result[0] = Affiliation(values["affiliation_id"].get(), values["name"].get(), values["unit"].get() or None, values["city"].get() or None, values["country"].get() or None, values["ror"].get() or None)
            dialog.destroy()
        ttk.Button(dialog, text="Valider", command=accept).grid(row=6, column=0, padx=6, pady=6)
        ttk.Button(dialog, text="Annuler", command=dialog.destroy).grid(row=6, column=1, padx=6, pady=6)
        dialog.transient(root); dialog.grab_set(); root.wait_window(dialog)
        return result[0]

    def add_person() -> None:
        nonlocal state
        if item := contributor_dialog():
            state = add_contributor(state, item); refresh_trees()
    def edit_person() -> None:
        nonlocal state
        selection = contributor_tree.selection()
        if selection and (item := next((value for value in state.metadata.contributors if value.contributor_id == selection[0]), None)) and (changed := contributor_dialog(item)):
            try:
                state = update_contributor(state, item.contributor_id, changed); refresh_trees()
            except ValueError as error:
                messagebox.showerror("Identifiant deja utilise", str(error), parent=root)
    def delete_person() -> None:
        nonlocal state
        if selection := contributor_tree.selection():
            state = remove_contributor(state, selection[0]); refresh_trees()
    def move_person(delta: int) -> None:
        nonlocal state
        if not (selection := contributor_tree.selection()): return
        values = list(state.metadata.contributors); index = next(i for i, value in enumerate(values) if value.contributor_id == selection[0]); target = index + delta
        if 0 <= target < len(values): values[index], values[target] = values[target], values[index]; state = replace(state, metadata=replace(state.metadata, contributors=tuple(values)), dirty=True); refresh_trees(); contributor_tree.selection_set(selection[0])
    def add_institution() -> None:
        nonlocal state
        if item := affiliation_dialog(): state = add_affiliation(state, item); refresh_trees()
    def edit_institution() -> None:
        nonlocal state
        selection = affiliation_tree.selection()
        if selection and (item := next((value for value in state.metadata.affiliations if value.affiliation_id == selection[0]), None)) and (changed := affiliation_dialog(item)):
            try:
                state = update_affiliation(state, item.affiliation_id, changed); refresh_trees()
            except ValueError as error:
                messagebox.showerror("Identifiant deja utilise", str(error), parent=root)
    def delete_institution() -> None:
        nonlocal state
        if selection := affiliation_tree.selection():
            try: state = remove_affiliation(state, selection[0]); refresh_trees()
            except ValueError as error: messagebox.showerror("Affiliation utilisée", str(error), parent=root)

    contributor_buttons = ttk.Frame(contributor_frame); contributor_buttons.grid(row=1, column=0, sticky="w", pady=4)
    for label, callback in (("Ajouter", add_person), ("Modifier", edit_person), ("Supprimer", delete_person), ("Monter", lambda: move_person(-1)), ("Descendre", lambda: move_person(1))): ttk.Button(contributor_buttons, text=label, command=callback).pack(side="left", padx=2)
    affiliation_buttons = ttk.Frame(affiliation_frame); affiliation_buttons.grid(row=1, column=0, sticky="w", pady=4)
    for label, callback in (("Ajouter", add_institution), ("Modifier", edit_institution), ("Supprimer", delete_institution)): ttk.Button(affiliation_buttons, text=label, command=callback).pack(side="left", padx=2)

    def save(close: bool = False) -> None:
        nonlocal state
        candidate = collect()
        validation = validate_metadata_editor_state(candidate)
        if not validation.valid:
            messagebox.showerror("Metadonnees invalides", "\n".join(f"[{item.code}] {item.message}" for item in validation.issues), parent=root)
            return
        if state.loaded_from_invalid_json and not messagebox.askyesno("JSON invalide", "Le fichier JSON existant est invalide. L'ecraser avec ces valeurs ?", parent=root):
            return
        try:
            state = save_metadata_editor_state(candidate)
        except OSError as error:
            messagebox.showerror("Echec d'enregistrement", str(error), parent=root)
            return
        refresh_trees()
        messagebox.showinfo("Mini-Metopes", f"Metadonnees enregistrees : {state.metadata_path}", parent=root)
        if close:
            root.destroy()

    ttk.Button(actions, text="Enregistrer", command=save).pack(side="left")
    ttk.Button(actions, text="Enregistrer et fermer", command=lambda: save(True)).pack(side="left", padx=5)
    def cancel() -> None:
        if collect().dirty and not messagebox.askyesno("Modifications non enregistrees", "Abandonner les modifications ?", parent=root): return
        root.destroy()
    ttk.Button(actions, text="Annuler", command=cancel).pack(side="right")
    refresh_trees()
    initializing = False
    root.protocol("WM_DELETE_WINDOW", cancel)
    root.mainloop()
    return 0
