"""Serialisation JSON deterministe du modele editorial."""

from __future__ import annotations

import json

from .model import (
    ColumnBreak,
    DrawingReference,
    EditorialBlock,
    EditorialBuildResult,
    EditorialInline,
    EditorialLink,
    EditorialNote,
    Heading,
    LineBreak,
    NoteReference,
    PageBreak,
    Paragraph,
    Tab,
    TextSpan,
)


def editorial_build_result_to_data(result: EditorialBuildResult) -> dict[str, object]:
    """Transformer le resultat en primitives JSON sans chemins locaux absolus."""
    return {
        "document": {
            "kind": result.document.kind,
            "source_name": result.document.source_name,
            "blocks": [_block_to_data(block) for block in result.document.blocks],
            "notes": [_note_to_data(note) for note in result.document.notes],
        },
        "diagnostics": [
            {
                "code": diagnostic.code,
                "severity": diagnostic.severity,
                "message": diagnostic.message,
                "paragraph_index": diagnostic.paragraph_index,
                "run_index": diagnostic.run_index,
                "style_id": diagnostic.style_id,
                "note_id": diagnostic.note_id,
            }
            for diagnostic in result.diagnostics
        ],
    }


def editorial_build_result_to_json(result: EditorialBuildResult) -> str:
    """Serialiser le resultat en JSON UTF-8 logique et reproductible."""
    return json.dumps(editorial_build_result_to_data(result), ensure_ascii=False, indent=2, sort_keys=True)


def _block_to_data(block: EditorialBlock) -> dict[str, object]:
    if isinstance(block, Heading):
        return {
            "kind": block.kind,
            "level": block.level,
            "content": [_inline_to_data(item) for item in block.content],
            "source_paragraph_index": block.source_paragraph_index,
            "source_style_id": block.source_style_id,
        }
    return {
        "kind": block.kind,
        "content": [_inline_to_data(item) for item in block.content],
        "source_paragraph_index": block.source_paragraph_index,
        "source_style_id": block.source_style_id,
    }


def _note_to_data(note: EditorialNote) -> dict[str, object]:
    return {
        "kind": note.kind,
        "note_id": note.note_id,
        "note_kind": note.note_kind,
        "blocks": [_block_to_data(block) for block in note.blocks],
    }


def _inline_to_data(item: EditorialInline) -> dict[str, object]:
    if isinstance(item, TextSpan):
        return {
            "kind": item.kind,
            "text": item.text,
            "marks": list(item.marks),
            "link": _link_to_data(item.link),
        }
    if isinstance(item, Tab):
        return {"kind": item.kind}
    if isinstance(item, LineBreak):
        return {"kind": item.kind}
    if isinstance(item, PageBreak):
        return {"kind": item.kind}
    if isinstance(item, ColumnBreak):
        return {"kind": item.kind}
    if isinstance(item, NoteReference):
        return {"kind": item.kind, "note_id": item.note_id, "note_kind": item.note_kind}
    if isinstance(item, DrawingReference):
        return {"kind": item.kind, "relationship_ids": list(item.relationship_ids)}
    raise TypeError(f"contenu editorial inconnu : {type(item)!r}")


def _link_to_data(link: EditorialLink | None) -> dict[str, object] | None:
    if link is None:
        return None
    return {
        "kind": link.kind,
        "target": link.target,
        "relationship_id": link.relationship_id,
        "anchor": link.anchor,
    }
