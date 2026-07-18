"""Serialisation JSON deterministe du modele editorial."""

from __future__ import annotations

import json

from .model import (
    ColumnBreak,
    DrawingReference,
    EditorialBlock,
    EditorialBuildResult,
    EditorialFigure,
    EditorialGraphic,
    EditorialInline,
    EditorialList,
    EditorialListItem,
    EditorialLink,
    EditorialNote,
    EditorialTable,
    EditorialTableCell,
    EditorialTableRow,
    Heading,
    LineBreak,
    NoteReference,
    PageBreak,
    Paragraph,
    ProseQuote,
    ProseQuoteParagraph,
    Tab,
    TextSpan,
    VerseLine,
    VerseQuote,
    VerseStanza,
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
    if isinstance(block, ProseQuote):
        return {
            "kind": block.kind,
            "paragraphs": [_prose_quote_paragraph_to_data(paragraph) for paragraph in block.paragraphs],
        }
    if isinstance(block, VerseQuote):
        return {
            "kind": block.kind,
            "stanzas": [_verse_stanza_to_data(stanza) for stanza in block.stanzas],
        }
    if isinstance(block, EditorialList):
        return _list_to_data(block)
    if isinstance(block, EditorialFigure):
        return _figure_to_data(block)
    if isinstance(block, EditorialTable):
        return _table_to_data(block)
    if isinstance(block, Paragraph):
        return {
            "kind": block.kind,
            "content": [_inline_to_data(item) for item in block.content],
            "source_paragraph_index": block.source_paragraph_index,
            "source_style_id": block.source_style_id,
            "rendition": block.rendition,
        }
    return {
        "kind": block.kind,
        "content": [_inline_to_data(item) for item in block.content],
        "source_paragraph_index": block.source_paragraph_index,
        "source_style_id": block.source_style_id,
    }


def _prose_quote_paragraph_to_data(paragraph: ProseQuoteParagraph) -> dict[str, object]:
    return {
        "kind": paragraph.kind,
        "content": [_inline_to_data(item) for item in paragraph.content],
        "source_paragraph_index": paragraph.source_paragraph_index,
        "source_style_id": paragraph.source_style_id,
    }


def _verse_stanza_to_data(stanza: VerseStanza) -> dict[str, object]:
    return {
        "kind": stanza.kind,
        "lines": [_verse_line_to_data(line) for line in stanza.lines],
        "source_paragraph_index": stanza.source_paragraph_index,
        "source_style_id": stanza.source_style_id,
    }


def _verse_line_to_data(line: VerseLine) -> dict[str, object]:
    return {
        "kind": line.kind,
        "content": [_inline_to_data(item) for item in line.content],
        "source_paragraph_index": line.source_paragraph_index,
        "line_index": line.line_index,
    }


def _list_to_data(editorial_list: EditorialList) -> dict[str, object]:
    return {
        "kind": editorial_list.kind,
        "list_kind": editorial_list.list_kind,
        "num_format": editorial_list.num_format,
        "start": editorial_list.start,
        "source_numbering_id": editorial_list.source_numbering_id,
        "source_level": editorial_list.source_level,
        "level_text": editorial_list.level_text,
        "suffix": editorial_list.suffix,
        "restart_after_level": editorial_list.restart_after_level,
        "items": [_list_item_to_data(item) for item in editorial_list.items],
    }


def _list_item_to_data(item: EditorialListItem) -> dict[str, object]:
    return {
        "kind": item.kind,
        "content": [_inline_to_data(inline) for inline in item.content],
        "child_lists": [_list_to_data(child) for child in item.child_lists],
        "source_paragraph_index": item.source_paragraph_index,
        "source_style_id": item.source_style_id,
        "continuation_paragraphs": [_block_to_data(paragraph) for paragraph in item.continuation_paragraphs],
    }


def _figure_to_data(figure: EditorialFigure) -> dict[str, object]:
    return {
        "kind": figure.kind,
        "graphic": _graphic_to_data(figure.graphic),
        "title": _block_to_data(figure.title) if figure.title is not None else None,
        "caption": _block_to_data(figure.caption) if figure.caption is not None else None,
        "credits": _block_to_data(figure.credits) if figure.credits is not None else None,
        "source_paragraph_index": figure.source_paragraph_index,
        "source_style_id": figure.source_style_id,
    }


def _table_to_data(table: EditorialTable) -> dict[str, object]:
    return {
        "kind": table.kind,
        "column_count": table.column_count,
        "source_block_index": table.source_block_index,
        "source_style_id": table.source_style_id,
        "rows": [_table_row_to_data(row) for row in table.rows],
    }


def _table_row_to_data(row: EditorialTableRow) -> dict[str, object]:
    return {
        "kind": row.kind,
        "role": row.role,
        "source_row_index": row.source_row_index,
        "cells": [_table_cell_to_data(cell) for cell in row.cells],
    }


def _table_cell_to_data(cell: EditorialTableCell) -> dict[str, object]:
    return {
        "kind": cell.kind,
        "role": cell.role,
        "content": [_inline_to_data(item) for item in cell.content],
        "source_row_index": cell.source_row_index,
        "source_column_index": cell.source_column_index,
    }


def _graphic_to_data(graphic: EditorialGraphic) -> dict[str, object]:
    return {
        "kind": graphic.kind,
        "source_part": graphic.source_part,
        "source_relationship_id": graphic.source_relationship_id,
        "source_media_path": graphic.source_media_path,
        "media_url": graphic.media_url,
        "content_type": graphic.content_type,
        "sha256": graphic.sha256,
        "description": graphic.description,
        "width_emu": graphic.width_emu,
        "height_emu": graphic.height_emu,
        "source_name": graphic.source_name,
        "source_title": graphic.source_title,
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
