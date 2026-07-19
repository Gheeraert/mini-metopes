"""Interface Tkinter d'edition des metadonnees associees a un DOCX.

Organisation en onglets sobres (Document, Auteurs, Publication, Resumes et
mots-cles, Droits et identifiants). Les listes repetables sont presentees en
tableaux synthetiques avec Ajouter / Modifier / Supprimer et, quand l'ordre
est significatif, Monter / Descendre. Toute la logique modifiable est dans
``metadata_controller`` ; ce module ne fait que la presentation.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from mini_metopes.docx import DocxInspectionError
from mini_metopes.metadata import (
    Abstract,
    Affiliation,
    Collection,
    Contributor,
    EditorialResponsibility,
    Identifier,
    KeywordGroup,
    License,
    Pagination,
    Publication,
    Publisher,
    Rights,
    default_metadata_path,
)

from .metadata_controller import (
    MetadataEditorState,
    add_affiliation,
    add_contributor,
    apply_profile_to_state,
    change_metadata_destination,
    is_metadata_dirty,
    load_metadata_editor_state,
    locate_source_document,
    move_item,
    next_identifier,
    remove_affiliation,
    remove_contributor,
    requires_save_as,
    save_metadata_editor_state,
    update_affiliation,
    update_contributor,
    update_metadata,
    validate_metadata_editor_state,
)

_ROLES = ("author", "editor", "translator", "scientific_editor", "other")
_DOCUMENT_TYPES = ("article", "chapter", "introduction", "conclusion", "bibliography", "other")
_IDENTIFIER_TYPES = ("doi", "isbn-13", "isbn-10", "issn", "eissn", "local")
_IDENTIFIER_FORMATS = ("", "print", "pdf", "epub", "html")
_ABSTRACT_TYPES = ("summary", "abstract", "back-cover")


def run_metadata_editor(docx_path: Path | None = None, metadata_path: Path | None = None) -> int:
    """Ouvrir explicitement l'editeur ; aucun Tkinter n'est lance a l'import."""
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    try:
        root = tk.Tk()
    except tk.TclError as error:
        print(f"ERREUR - impossible d'initialiser l'interface graphique : {error}")
        return 2
    root.title("Mini-Metopes — Metadonnees")
    root.minsize(880, 620)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    state: MetadataEditorState | None = None

    notebook = ttk.Notebook(root)
    notebook.grid(row=0, column=0, sticky="nsew", padx=8, pady=6)
    actions = ttk.Frame(root, padding=8)
    actions.grid(row=1, column=0, sticky="ew")
    save_label_var = tk.StringVar(value="Enregistrer sous…")

    def scrollable_tab(title: str) -> ttk.Frame:
        container = ttk.Frame(notebook)
        notebook.add(container, text=title)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)
        canvas = tk.Canvas(container, highlightthickness=0)
        bar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, padding=8)
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(inner_id, width=e.width))
        canvas.configure(yscrollcommand=bar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        bar.grid(row=0, column=1, sticky="ns")
        inner.columnconfigure(1, weight=1)
        return inner

    # ------------------------------------------------------------------ utils

    def form_dialog(title: str, fields: list[tuple[str, str, str]], values: dict[str, str]) -> dict[str, str] | None:
        """Petit formulaire modal generique ; kind = entry, combo:a|b, text."""
        dialog = tk.Toplevel(root)
        dialog.title(title)
        variables: dict[str, object] = {}
        for row, (label, key, kind) in enumerate(fields):
            ttk.Label(dialog, text=label).grid(row=row, column=0, sticky="nw", padx=6, pady=2)
            if kind.startswith("combo:"):
                variable = tk.StringVar(value=values.get(key, ""))
                ttk.Combobox(dialog, textvariable=variable, values=kind[6:].split("|"), width=34, state="readonly").grid(row=row, column=1, padx=6, pady=2, sticky="ew")
                variables[key] = variable
            elif kind == "text":
                widget = tk.Text(dialog, height=6, width=48, wrap="word")
                widget.insert("1.0", values.get(key, ""))
                widget.grid(row=row, column=1, padx=6, pady=2, sticky="ew")
                variables[key] = widget
            else:
                variable = tk.StringVar(value=values.get(key, ""))
                ttk.Entry(dialog, textvariable=variable, width=36).grid(row=row, column=1, padx=6, pady=2, sticky="ew")
                variables[key] = variable
        result: list[dict[str, str] | None] = [None]

        def accept() -> None:
            collected: dict[str, str] = {}
            for key, variable in variables.items():
                collected[key] = variable.get("1.0", "end-1c") if isinstance(variable, tk.Text) else variable.get()
            result[0] = collected
            dialog.destroy()

        buttons = ttk.Frame(dialog)
        buttons.grid(row=len(fields), column=0, columnspan=2, pady=6)
        ttk.Button(buttons, text="Valider", command=accept).pack(side="left", padx=4)
        ttk.Button(buttons, text="Annuler", command=dialog.destroy).pack(side="left", padx=4)
        dialog.columnconfigure(1, weight=1)
        dialog.transient(root)
        dialog.grab_set()
        root.wait_window(dialog)
        return result[0]

    def list_frame(parent: ttk.Frame, title: str, columns: tuple[tuple[str, str], ...], *, orderable: bool = False):
        frame = ttk.LabelFrame(parent, text=title, padding=5)
        tree = ttk.Treeview(frame, columns=tuple(key for key, _ in columns), show="headings", height=5)
        for key, heading in columns:
            tree.heading(key, text=heading)
            tree.column(key, width=120, anchor="w")
        tree.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=0, sticky="w", pady=4)
        return frame, tree, buttons

    def selected_index(tree) -> int | None:
        selection = tree.selection()
        if not selection:
            return None
        return tree.index(selection[0])

    # -------------------------------------------------------------- onglet 1

    document_tab = scrollable_tab("Document")
    paths_frame = ttk.LabelFrame(document_tab, text="Fichiers", padding=6)
    paths_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
    paths_frame.columnconfigure(1, weight=1)
    docx_label_var = tk.StringVar()
    json_label_var = tk.StringVar()
    ttk.Label(paths_frame, text="DOCX :").grid(row=0, column=0, sticky="w")
    ttk.Label(paths_frame, textvariable=docx_label_var).grid(row=0, column=1, sticky="w")
    ttk.Label(paths_frame, text="JSON :").grid(row=1, column=0, sticky="w")
    ttk.Label(paths_frame, textvariable=json_label_var).grid(row=1, column=1, sticky="w")

    def relocate() -> None:
        nonlocal state
        selected = filedialog.askopenfilename(parent=root, filetypes=[("Documents Word", "*.docx *.DOCX")])
        if not selected:
            return
        from .metadata_controller import relocate_source_document

        state = relocate_source_document(collect(), Path(selected))
        refresh_all()

    ttk.Button(paths_frame, text="Relocaliser le DOCX…", command=relocate).grid(row=0, column=2, padx=6)

    general = ttk.LabelFrame(document_tab, text="Document", padding=6)
    general.grid(row=1, column=0, columnspan=2, sticky="ew", pady=6)
    general.columnconfigure(1, weight=1)
    title_var = tk.StringVar()
    subtitle_var = tk.StringVar()
    language_var = tk.StringVar()
    type_var = tk.StringVar()
    for row, (label, variable) in enumerate((("Titre", title_var), ("Sous-titre", subtitle_var), ("Langue (BCP 47)", language_var))):
        ttk.Label(general, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Entry(general, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=2)
    ttk.Label(general, text="Type").grid(row=3, column=0, sticky="w", pady=2)
    ttk.Combobox(general, textvariable=type_var, values=_DOCUMENT_TYPES, state="readonly").grid(row=3, column=1, sticky="w", pady=2)

    diagnostics_frame = ttk.LabelFrame(document_tab, text="Diagnostics", padding=6)
    diagnostics_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=6)
    diagnostics_frame.columnconfigure(0, weight=1)
    diagnostics_tree = ttk.Treeview(diagnostics_frame, columns=("severity", "path", "message"), show="headings", height=6)
    for key, heading, width in (("severity", "Niveau", 80), ("path", "Emplacement", 200), ("message", "Message", 420)):
        diagnostics_tree.heading(key, text=heading)
        diagnostics_tree.column(key, width=width, anchor="w")
    diagnostics_tree.grid(sticky="nsew")

    # -------------------------------------------------------------- onglet 2

    authors_tab = scrollable_tab("Auteurs")
    contributors_frame, contributor_tree, contributor_buttons = list_frame(
        authors_tab, "Auteurs et contributeurs (ordre significatif)",
        (("role", "Rôle"), ("name", "Nom"), ("orcid", "ORCID"), ("affiliations", "Affiliations")),
    )
    contributors_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")
    affiliations_frame, affiliation_tree, affiliation_buttons = list_frame(
        authors_tab, "Affiliations",
        (("id", "Identifiant"), ("name", "Institution"), ("city", "Ville"), ("ror", "ROR")),
    )
    affiliations_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=6)

    def contributor_dialog(current: Contributor | None) -> Contributor | None:
        values = {
            "id": current.contributor_id if current else next_identifier("person", tuple(item.contributor_id for item in state.metadata.contributors)),
            "role": current.role if current else "author",
            "role_label": (current.role_label if current else None) or "",
            "given_name": (current.given_name if current else None) or "",
            "family_name": (current.family_name if current else None) or "",
            "literal_name": (current.literal_name if current else None) or "",
            "orcid": (current.orcid if current else None) or "",
            "email": (current.email if current else None) or "",
            "affiliations": ", ".join(current.affiliation_ids) if current else "",
        }
        collected = form_dialog("Contributeur", [
            ("Identifiant", "id", "entry"),
            ("Rôle", "role", "combo:" + "|".join(_ROLES)),
            ("Libellé (rôle other)", "role_label", "entry"),
            ("Prénom", "given_name", "entry"),
            ("Nom", "family_name", "entry"),
            ("Nom littéral", "literal_name", "entry"),
            ("ORCID", "orcid", "entry"),
            ("Courriel", "email", "entry"),
            ("Affiliations (IDs, virgules)", "affiliations", "entry"),
        ], values)
        if collected is None:
            return None
        return Contributor(
            contributor_id=collected["id"],
            role=collected["role"],
            given_name=collected["given_name"] or None,
            family_name=collected["family_name"] or None,
            literal_name=collected["literal_name"] or None,
            orcid=collected["orcid"] or None,
            email=collected["email"] or None,
            role_label=collected["role_label"] or None,
            affiliation_ids=tuple(value.strip() for value in collected["affiliations"].split(",") if value.strip()),
        )

    def affiliation_dialog(current: Affiliation | None) -> Affiliation | None:
        values = {
            "id": current.affiliation_id if current else next_identifier("affiliation", tuple(item.affiliation_id for item in state.metadata.affiliations)),
            "name": current.name if current else "",
            "unit": (current.unit if current else None) or "",
            "city": (current.city if current else None) or "",
            "country": (current.country if current else None) or "",
            "ror": (current.ror if current else None) or "",
        }
        collected = form_dialog("Affiliation", [
            ("Identifiant", "id", "entry"), ("Institution", "name", "entry"), ("Unité", "unit", "entry"),
            ("Ville", "city", "entry"), ("Pays", "country", "entry"), ("ROR (URL)", "ror", "entry"),
        ], values)
        if collected is None:
            return None
        return Affiliation(collected["id"], collected["name"], collected["unit"] or None,
                           collected["city"] or None, collected["country"] or None, collected["ror"] or None)

    # -------------------------------------------------------------- onglet 3

    publication_tab = scrollable_tab("Publication")
    publisher_frame = ttk.LabelFrame(publication_tab, text="Éditeur (les valeurs stables peuvent venir d'un profil)", padding=6)
    publisher_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
    publisher_frame.columnconfigure(1, weight=1)
    publisher_name_var = tk.StringVar()
    publisher_place_var = tk.StringVar()
    publisher_url_var = tk.StringVar()
    publication_date_var = tk.StringVar()
    for row, (label, variable) in enumerate((("Nom", publisher_name_var), ("Lieu", publisher_place_var), ("URL", publisher_url_var), ("Date de publication", publication_date_var))):
        ttk.Label(publisher_frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Entry(publisher_frame, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=2)
    ttk.Label(publisher_frame, text="Adresse (une ligne par ligne)").grid(row=4, column=0, sticky="nw", pady=2)
    publisher_address_text = tk.Text(publisher_frame, height=3, width=48)
    publisher_address_text.grid(row=4, column=1, sticky="ew", pady=2)

    def apply_profile() -> None:
        nonlocal state
        selected = filedialog.askopenfilename(parent=root, filetypes=[("Profil institutionnel", "*.json")])
        if not selected:
            return
        state = apply_profile_to_state(collect(), Path(selected))
        refresh_all()

    ttk.Button(publisher_frame, text="Appliquer un profil…", command=apply_profile).grid(row=5, column=1, sticky="w", pady=4)

    responsibility_frame, responsibility_tree, responsibility_buttons = list_frame(
        publication_tab, "Responsables d'édition (suivi éditorial)",
        (("responsibility", "Responsabilité"), ("name", "Nom")), orderable=True,
    )
    responsibility_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=6)

    collection_frame = ttk.LabelFrame(publication_tab, text="Collection (simple)", padding=6)
    collection_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
    collection_frame.columnconfigure(1, weight=1)
    collection_title_var = tk.StringVar()
    collection_issn_var = tk.StringVar()
    collection_volume_var = tk.StringVar()
    for row, (label, variable) in enumerate((("Titre", collection_title_var), ("ISSN", collection_issn_var), ("Volume", collection_volume_var))):
        ttk.Label(collection_frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Entry(collection_frame, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=2)

    pagination_frame = ttk.LabelFrame(publication_tab, text="Pagination (bornes ou étendue, exclusives)", padding=6)
    pagination_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=6)
    page_from_var = tk.StringVar()
    page_to_var = tk.StringVar()
    extent_var = tk.StringVar()
    for column, (label, variable) in enumerate((("De la page", page_from_var), ("à la page", page_to_var), ("ou étendue (pages)", extent_var))):
        ttk.Label(pagination_frame, text=label).grid(row=0, column=column * 2, sticky="w", padx=(0, 4))
        ttk.Entry(pagination_frame, textvariable=variable, width=8).grid(row=0, column=column * 2 + 1, padx=(0, 12))

    # -------------------------------------------------------------- onglet 4

    texts_tab = scrollable_tab("Résumés et mots-clés")
    abstracts_frame, abstract_tree, abstract_buttons = list_frame(
        texts_tab, "Résumés et quatrième de couverture (ordre conservé)",
        (("type", "Type"), ("language", "Langue"), ("excerpt", "Début du texte")), orderable=True,
    )
    abstracts_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")
    keywords_frame, keyword_tree, keyword_buttons = list_frame(
        texts_tab, "Groupes de mots-clés (ordre conservé)",
        (("language", "Langue"), ("scheme", "Schéma"), ("items", "Mots-clés")), orderable=True,
    )
    keywords_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=6)

    def abstract_dialog(current: Abstract | None) -> Abstract | None:
        values = {
            "type": current.abstract_type if current else "summary",
            "language": current.language if current else (language_var.get() or "fr"),
            "text": current.text if current else "",
        }
        collected = form_dialog("Résumé", [
            ("Type", "type", "combo:" + "|".join(_ABSTRACT_TYPES)),
            ("Langue", "language", "entry"),
            ("Texte (un paragraphe par ligne)", "text", "text"),
        ], values)
        if collected is None:
            return None
        return Abstract(collected["type"], collected["language"], collected["text"])

    def keyword_dialog(current: KeywordGroup | None) -> KeywordGroup | None:
        values = {
            "language": current.language if current else (language_var.get() or "fr"),
            "scheme": current.scheme if current else "keywords",
            "items": "\n".join(current.items) if current else "",
        }
        collected = form_dialog("Groupe de mots-clés", [
            ("Langue", "language", "entry"),
            ("Schéma", "scheme", "entry"),
            ("Mots-clés (un par ligne)", "items", "text"),
        ], values)
        if collected is None:
            return None
        return KeywordGroup(
            collected["language"],
            tuple(line.strip() for line in collected["items"].splitlines() if line.strip()),
            collected["scheme"] or "keywords",
        )

    def responsibility_dialog(current: EditorialResponsibility | None) -> EditorialResponsibility | None:
        values = {"responsibility": current.responsibility if current else "", "name": current.name if current else ""}
        collected = form_dialog("Responsable d'édition", [
            ("Responsabilité (ex. éditrice)", "responsibility", "entry"),
            ("Nom", "name", "entry"),
        ], values)
        if collected is None:
            return None
        return EditorialResponsibility(collected["responsibility"], collected["name"])

    # -------------------------------------------------------------- onglet 5

    rights_tab = scrollable_tab("Droits et identifiants")
    rights_frame = ttk.LabelFrame(rights_tab, text="Droits et licence", padding=6)
    rights_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
    rights_frame.columnconfigure(1, weight=1)
    holder_var = tk.StringVar()
    statement_var = tk.StringVar()
    license_name_var = tk.StringVar()
    license_url_var = tk.StringVar()
    for row, (label, variable) in enumerate((("Détenteur des droits", holder_var), ("Mention affichée", statement_var), ("Licence (nom)", license_name_var), ("Licence (URL)", license_url_var))):
        ttk.Label(rights_frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Entry(rights_frame, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=2)

    identifiers_frame, identifier_tree, identifier_buttons = list_frame(
        rights_tab, "Identifiants de publication",
        (("type", "Type"), ("value", "Valeur"), ("format", "Support")), orderable=True,
    )
    identifiers_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=6)

    def identifier_dialog(current: Identifier | None) -> Identifier | None:
        values = {
            "type": current.identifier_type if current else "doi",
            "value": current.value if current else "",
            "format": (current.identifier_format if current else None) or "",
        }
        collected = form_dialog("Identifiant", [
            ("Type", "type", "combo:" + "|".join(_IDENTIFIER_TYPES)),
            ("Valeur", "value", "entry"),
            ("Support", "format", "combo:" + "|".join(_IDENTIFIER_FORMATS)),
        ], values)
        if collected is None:
            return None
        return Identifier(collected["type"], collected["value"], collected["format"] or None)

    # ------------------------------------------------------------ etat <-> UI

    def collect() -> MetadataEditorState:
        nonlocal state

        def parse_int(value: str) -> int | None:
            value = value.strip()
            return int(value) if value.isdigit() else (None if not value else -1)

        pagination = None
        if page_from_var.get().strip() or page_to_var.get().strip():
            pagination = Pagination(page_from=parse_int(page_from_var.get()), page_to=parse_int(page_to_var.get()))
        elif extent_var.get().strip():
            pagination = Pagination(extent=parse_int(extent_var.get()))
        collection = None
        if collection_title_var.get().strip() or collection_issn_var.get().strip() or collection_volume_var.get().strip():
            collection = Collection(
                title=collection_title_var.get(),
                issn=collection_issn_var.get().strip() or None,
                volume=collection_volume_var.get().strip() or None,
            )
        metadata = replace(
            state.metadata,
            title=title_var.get(),
            subtitle=subtitle_var.get() or None,
            language=language_var.get(),
            document_type=type_var.get(),
            publication=Publication(
                publisher=Publisher(
                    name=publisher_name_var.get().strip() or None,
                    place=publisher_place_var.get().strip() or None,
                    address=tuple(line for line in publisher_address_text.get("1.0", "end-1c").splitlines() if line.strip()),
                    url=publisher_url_var.get().strip() or None,
                ),
                publication_date=publication_date_var.get().strip() or None,
            ),
            rights=Rights(
                holder=holder_var.get().strip() or None,
                statement=statement_var.get().strip() or None,
                license=License(
                    name=license_name_var.get().strip() or None,
                    url=license_url_var.get().strip() or None,
                ),
            ),
            collection=collection,
            pagination=pagination,
        )
        state = replace(state, metadata=metadata, dirty=is_metadata_dirty(state.saved_metadata, metadata))
        return state

    def refresh_lists() -> None:
        diagnostics_tree.delete(*diagnostics_tree.get_children())
        if state.loaded_from_invalid_json:
            diagnostics_tree.insert("", "end", values=("ERROR", "metadata", "JSON existant invalide ; valeurs de secours affichees"))
        for issue in state.issues:
            diagnostics_tree.insert("", "end", values=(issue.severity.upper(), issue.path or "", f"[{issue.code}] {issue.message}"))
        contributor_tree.delete(*contributor_tree.get_children())
        for item in state.metadata.contributors:
            name = item.literal_name or " ".join(part for part in (item.given_name, item.family_name) if part)
            contributor_tree.insert("", "end", iid=item.contributor_id,
                                    values=(item.role, name, item.orcid or "", ", ".join(item.affiliation_ids)))
        affiliation_tree.delete(*affiliation_tree.get_children())
        for item in state.metadata.affiliations:
            affiliation_tree.insert("", "end", iid=item.affiliation_id,
                                    values=(item.affiliation_id, item.name, item.city or "", item.ror or ""))
        responsibility_tree.delete(*responsibility_tree.get_children())
        for index, item in enumerate(state.metadata.editorial_responsibility):
            responsibility_tree.insert("", "end", iid=str(index), values=(item.responsibility, item.name))
        abstract_tree.delete(*abstract_tree.get_children())
        for index, item in enumerate(state.metadata.abstracts):
            excerpt = item.text.replace("\n", " ")
            abstract_tree.insert("", "end", iid=str(index), values=(item.abstract_type, item.language, excerpt[:60]))
        keyword_tree.delete(*keyword_tree.get_children())
        for index, group in enumerate(state.metadata.keywords):
            keyword_tree.insert("", "end", iid=str(index), values=(group.language, group.scheme, ", ".join(group.items)))
        identifier_tree.delete(*identifier_tree.get_children())
        for index, item in enumerate(state.metadata.identifiers):
            identifier_tree.insert("", "end", iid=str(index), values=(item.identifier_type, item.value, item.identifier_format or ""))

    def refresh_all() -> None:
        docx_label_var.set(str(state.docx_path))
        json_label_var.set(str(state.metadata_path))
        title_var.set(state.metadata.title)
        subtitle_var.set(state.metadata.subtitle or "")
        language_var.set(state.metadata.language)
        type_var.set(state.metadata.document_type)
        publisher = state.metadata.publication.publisher
        publisher_name_var.set(publisher.name or "")
        publisher_place_var.set(publisher.place or "")
        publisher_url_var.set(publisher.url or "")
        publication_date_var.set(state.metadata.publication.publication_date or "")
        publisher_address_text.delete("1.0", "end")
        publisher_address_text.insert("1.0", "\n".join(publisher.address))
        holder_var.set(state.metadata.rights.holder or "")
        statement_var.set(state.metadata.rights.statement or "")
        license_name_var.set(state.metadata.rights.license.name or "")
        license_url_var.set(state.metadata.rights.license.url or "")
        collection = state.metadata.collection
        collection_title_var.set(collection.title if collection else "")
        collection_issn_var.set((collection.issn if collection else None) or "")
        collection_volume_var.set((collection.volume if collection else None) or "")
        pagination = state.metadata.pagination
        page_from_var.set(str(pagination.page_from) if pagination and pagination.page_from is not None else "")
        page_to_var.set(str(pagination.page_to) if pagination and pagination.page_to is not None else "")
        extent_var.set(str(pagination.extent) if pagination and pagination.extent is not None else "")
        save_label_var.set("Enregistrer sous…" if requires_save_as(state) else "Enregistrer")
        refresh_lists()

    # -------------------------------------------------- operations de listes

    def sequence_actions(tree, field: str, dialog, buttons, *, orderable: bool = True) -> None:
        """Cabler Ajouter/Modifier/Supprimer/Monter/Descendre sur une liste."""

        def current_items() -> tuple:
            return getattr(state.metadata, field)

        def set_items(items: tuple) -> None:
            nonlocal state
            state = update_metadata(state, **{field: items})
            refresh_lists()

        def add() -> None:
            if item := dialog(None):
                set_items(current_items() + (item,))

        def edit() -> None:
            index = selected_index(tree)
            if index is not None and (changed := dialog(current_items()[index])):
                items = list(current_items())
                items[index] = changed
                set_items(tuple(items))

        def delete() -> None:
            index = selected_index(tree)
            if index is not None:
                items = list(current_items())
                del items[index]
                set_items(tuple(items))

        def move(delta: int) -> None:
            index = selected_index(tree)
            if index is not None:
                set_items(move_item(current_items(), index, delta))
                children = tree.get_children()
                target = index + delta
                if 0 <= target < len(children):
                    tree.selection_set(children[target])

        entries = [("Ajouter", add), ("Modifier", edit), ("Supprimer", delete)]
        if orderable:
            entries += [("Monter", lambda: move(-1)), ("Descendre", lambda: move(1))]
        for label, callback in entries:
            ttk.Button(buttons, text=label, command=callback).pack(side="left", padx=2)

    sequence_actions(responsibility_tree, "editorial_responsibility", responsibility_dialog, responsibility_buttons)
    sequence_actions(abstract_tree, "abstracts", abstract_dialog, abstract_buttons)
    sequence_actions(keyword_tree, "keywords", keyword_dialog, keyword_buttons)
    sequence_actions(identifier_tree, "identifiers", identifier_dialog, identifier_buttons)

    def add_person() -> None:
        nonlocal state
        if item := contributor_dialog(None):
            try:
                state = add_contributor(state, item)
                refresh_lists()
            except ValueError as error:
                messagebox.showerror("Identifiant invalide", str(error), parent=root)

    def edit_person() -> None:
        nonlocal state
        selection = contributor_tree.selection()
        if selection and (item := next((value for value in state.metadata.contributors if value.contributor_id == selection[0]), None)) and (changed := contributor_dialog(item)):
            try:
                state = update_contributor(state, item.contributor_id, changed)
                refresh_lists()
            except ValueError as error:
                messagebox.showerror("Identifiant deja utilise", str(error), parent=root)

    def delete_person() -> None:
        nonlocal state
        if selection := contributor_tree.selection():
            state = remove_contributor(state, selection[0])
            refresh_lists()

    def move_person(delta: int) -> None:
        nonlocal state
        if not (selection := contributor_tree.selection()):
            return
        index = next(i for i, value in enumerate(state.metadata.contributors) if value.contributor_id == selection[0])
        state = update_metadata(state, contributors=move_item(state.metadata.contributors, index, delta))
        refresh_lists()
        contributor_tree.selection_set(selection[0])

    def add_institution() -> None:
        nonlocal state
        if item := affiliation_dialog(None):
            try:
                state = add_affiliation(state, item)
                refresh_lists()
            except ValueError as error:
                messagebox.showerror("Identifiant invalide", str(error), parent=root)

    def edit_institution() -> None:
        nonlocal state
        selection = affiliation_tree.selection()
        if selection and (item := next((value for value in state.metadata.affiliations if value.affiliation_id == selection[0]), None)) and (changed := affiliation_dialog(item)):
            try:
                state = update_affiliation(state, item.affiliation_id, changed)
                refresh_lists()
            except ValueError as error:
                messagebox.showerror("Identifiant deja utilise", str(error), parent=root)

    def delete_institution() -> None:
        nonlocal state
        if selection := affiliation_tree.selection():
            try:
                state = remove_affiliation(state, selection[0])
                refresh_lists()
            except ValueError as error:
                messagebox.showerror("Affiliation utilisée", str(error), parent=root)

    for label, callback in (("Ajouter", add_person), ("Modifier", edit_person), ("Supprimer", delete_person), ("Monter", lambda: move_person(-1)), ("Descendre", lambda: move_person(1))):
        ttk.Button(contributor_buttons, text=label, command=callback).pack(side="left", padx=2)
    for label, callback in (("Ajouter", add_institution), ("Modifier", edit_institution), ("Supprimer", delete_institution)):
        ttk.Button(affiliation_buttons, text=label, command=callback).pack(side="left", padx=2)

    # ---------------------------------------------------------------- actions

    def save(close: bool = False) -> None:
        nonlocal state
        candidate = collect()
        validation = validate_metadata_editor_state(candidate)
        if not validation.valid:
            messagebox.showerror("Metadonnees invalides", "\n".join(f"[{item.code}] {item.message}" for item in validation.issues if item.severity == "error"), parent=root)
            return
        if candidate.loaded_from_invalid_json and not messagebox.askyesno("JSON invalide", "Le fichier JSON existant est invalide. L'ecraser avec ces valeurs ?", parent=root):
            return
        if requires_save_as(candidate):
            suggested = default_metadata_path(candidate.docx_path)
            selected = filedialog.asksaveasfilename(
                parent=root,
                title="Enregistrer les metadonnees sous…",
                initialdir=str(suggested.parent),
                initialfile=suggested.name,
                defaultextension=".json",
                filetypes=[("Metadonnees JSON", "*.json")],
            )
            if not selected:
                return
            candidate = change_metadata_destination(candidate, Path(selected))
        try:
            state = save_metadata_editor_state(candidate)
        except OSError as error:
            messagebox.showerror("Echec d'enregistrement", str(error), parent=root)
            return
        refresh_all()
        messagebox.showinfo("Mini-Metopes", f"Metadonnees enregistrees : {state.metadata_path}", parent=root)
        if close:
            root.destroy()

    def load_configuration() -> None:
        nonlocal state
        selected = filedialog.askopenfilename(parent=root, filetypes=[("Metadonnees JSON", "*.json")])
        if not selected:
            return
        json_path = Path(selected)
        docx, issues = locate_source_document(json_path)
        if docx is None:
            if issues and issues[0].code != "source_document_not_found":
                messagebox.showerror("JSON invalide", "\n".join(f"[{item.code}] {item.message}" for item in issues), parent=root)
                return
            if not messagebox.askyesno("DOCX introuvable", "Le DOCX reference est introuvable. Le relocaliser ?", parent=root):
                return
            relocated = filedialog.askopenfilename(parent=root, filetypes=[("Documents Word", "*.docx *.DOCX")])
            if not relocated:
                return
            docx = Path(relocated)
        state = load_metadata_editor_state(docx, json_path)
        if docx.name != Path(state.metadata.source.path).name:
            from .metadata_controller import relocate_source_document

            state = relocate_source_document(state, docx)
        refresh_all()

    ttk.Button(actions, textvariable=save_label_var, command=save).pack(side="left")
    ttk.Button(actions, text="Enregistrer et fermer", command=lambda: save(True)).pack(side="left", padx=5)
    ttk.Button(actions, text="Charger…", command=load_configuration).pack(side="left", padx=5)

    def cancel() -> None:
        if state is not None and collect().dirty and not messagebox.askyesno("Modifications non enregistrees", "Abandonner les modifications ?", parent=root):
            return
        root.destroy()

    ttk.Button(actions, text="Annuler", command=cancel).pack(side="right")
    root.protocol("WM_DELETE_WINDOW", cancel)

    pending_error: list[Exception] = []

    def choose_initial_docx() -> None:
        nonlocal docx_path, state
        if docx_path is None:
            selected = filedialog.askopenfilename(
                parent=root, filetypes=[("Documents Word", "*.docx *.DOCX")],
            )
            if not selected:
                root.destroy()
                return
            docx_path = Path(selected)
        try:
            state = load_metadata_editor_state(docx_path, metadata_path)
        except (DocxInspectionError, OSError) as error:
            pending_error.append(error)
            root.destroy()
            return
        refresh_all()

    root.after_idle(choose_initial_docx)
    root.mainloop()
    if pending_error:
        raise pending_error[0]
    return 0
