"""Type de resultat public de l'editeur de metadonnees, sans dependance Tkinter.

Isole de ``metadata_editor`` pour que ``from mini_metopes.gui import
MetadataEditorResult`` (typage cote appelant) n'entraine aucun import
Tkinter differe.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

MetadataEditorStatus = Literal["saved", "cancelled"]


@dataclass(frozen=True, slots=True)
class MetadataEditorResult:
    """Bilan d'une session d'edition, renvoye a la fermeture de la fenetre.

    ``status`` vaut ``"saved"`` uniquement apres un « Enregistrer et fermer »
    reussi : un simple clic sur « Enregistrer » ecrit deja le JSON mais ne
    cloture pas la session (aucun resultat n'est encore produit), et une
    annulation reste ``"cancelled"`` meme si un enregistrement precedent a
    laisse un JSON valide sur disque.
    """

    status: MetadataEditorStatus
    docx_path: Path
    metadata_path: Path | None

    @property
    def saved(self) -> bool:
        """Raccourci pratique pour ``status == "saved"`` avec un chemin connu."""
        return self.status == "saved" and self.metadata_path is not None
