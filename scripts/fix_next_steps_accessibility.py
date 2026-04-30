#!/usr/bin/env python3
"""
Apply accessibility and style fixes to petition_to_seal_eviction_next_steps.docx:
  - Replace the title table with a Title-styled paragraph
  - Remove the empty Normal paragraph that follows the table
  - Update Heading 2 color from bright blue (0074F1) to darker navy (17406D)
  - Update Title style with dark navy background, top/bottom borders, and white text
  - Update TitleChar style to match Title changes

Run from the repository root:
    python scripts/fix_next_steps_accessibility.py
    python scripts/fix_next_steps_accessibility.py path/to/input.docx path/to/output.docx
"""

import argparse
import os
import shutil
import sys
import tempfile
import zipfile

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DEFAULT_INPUT = os.path.join(
    "docassemble",
    "MAPetitionToSealEviction",
    "data",
    "templates",
    "petition_to_seal_eviction_next_steps.docx",
)

DARKER_NAVY = "17406D"
WHITE = "FFFFFF"


def w(tag):
    return f"{{{W}}}{tag}"


def make_title_paragraph(title_text):
    """Build a centered Title-style paragraph containing title_text."""
    p = etree.Element(w("p"))
    pPr = etree.SubElement(p, w("pPr"))
    pStyle = etree.SubElement(pPr, w("pStyle"))
    pStyle.set(w("val"), "Title")
    jc = etree.SubElement(pPr, w("jc"))
    jc.set(w("val"), "center")
    r = etree.SubElement(p, w("r"))
    t = etree.SubElement(r, w("t"))
    t.text = title_text
    return p


def fix_document(content: bytes) -> bytes:
    """
    Replace the leading title table with a Title paragraph and drop the
    empty Normal paragraph that Word inserts after a table.
    """
    doc = etree.fromstring(content)
    body = doc.find(w("body"))

    if not len(body) or body[0].tag != w("tbl"):
        print(
            "Warning: first body element is not a table; skipping document structure change.",
            file=sys.stderr,
        )
        return _serialize(doc)

    title_text = "".join(t.text or "" for t in body[0].iter(w("t")))
    body.remove(body[0])
    body.insert(0, make_title_paragraph(title_text))

    # Remove the empty Normal paragraph Word adds after a table, if present.
    if len(body) > 1 and body[1].tag == w("p"):
        style_el = body[1].find(f".//{w('pStyle')}")
        style_val = style_el.get(w("val")) if style_el is not None else "Normal"
        text = "".join(t.text or "" for t in body[1].iter(w("t")))
        if not text.strip() and style_val == "Normal":
            body.remove(body[1])

    return _serialize(doc)


def fix_styles(content: bytes) -> bytes:
    """
    Update Heading2, Heading2Char, Title and TitleChar style definitions.
    """
    styles_root = etree.fromstring(content)

    for style in styles_root.findall(f".//{w('style')}"):
        sid = style.get(w("styleId"), "")

        if sid == "Heading2":
            _update_heading2(style)
        elif sid == "Heading2Char":
            _update_heading2_char(style)
        elif sid == "Title":
            _update_title(style)
        elif sid == "TitleChar":
            _update_title_char(style)

    return _serialize(styles_root)


# ---------------------------------------------------------------------------
# Style-level helpers
# ---------------------------------------------------------------------------

def _update_heading2(style):
    """Change Heading 2 border and text color from 0074F1 to DARKER_NAVY."""
    pPr = style.find(w("pPr"))
    if pPr is not None:
        bottom = pPr.find(f".//{w('bottom')}")
        if bottom is not None:
            bottom.set(w("color"), DARKER_NAVY)
            bottom.set(w("themeColor"), "text2")

    rPr = style.find(w("rPr"))
    if rPr is not None:
        color = rPr.find(w("color"))
        if color is not None:
            color.set(w("val"), DARKER_NAVY)
            color.set(w("themeColor"), "text2")


def _update_heading2_char(style):
    """Change Heading 2 Char text color from 0074F1 to DARKER_NAVY."""
    rPr = style.find(w("rPr"))
    if rPr is not None:
        color = rPr.find(w("color"))
        if color is not None:
            color.set(w("val"), DARKER_NAVY)
            color.set(w("themeColor"), "text2")


def _update_title(style):
    """
    Add dark navy background fill + top/bottom borders to Title paragraph
    properties, and change text color to white.
    """
    pPr = _ensure_child(style, w("pPr"))

    # --- borders ---
    pBdr = _ensure_child(pPr, w("pBdr"))
    for side in ("top", "bottom"):
        border = _ensure_child(pBdr, w(side))
        border.set(w("val"), "single")
        border.set(w("sz"), "48")
        border.set(w("space"), "1")
        border.set(w("color"), DARKER_NAVY)
        border.set(w("themeColor"), "text2")

    # --- paragraph shading (fill) ---
    shd = _ensure_child(pPr, w("shd"))
    shd.set(w("val"), "clear")
    shd.set(w("color"), "auto")
    shd.set(w("fill"), DARKER_NAVY)
    shd.set(w("themeFill"), "text2")

    # --- run text color ---
    rPr = style.find(w("rPr"))
    if rPr is not None:
        color = rPr.find(w("color"))
        if color is not None:
            color.set(w("val"), WHITE)
            color.set(w("themeColor"), "background1")
            color.attrib.pop(w("themeShade"), None)
            color.attrib.pop(w("themeTint"), None)


def _update_title_char(style):
    """
    Change TitleChar text color to white and add matching shading so the
    linked character style mirrors the Title paragraph style changes.
    """
    rPr = style.find(w("rPr"))
    if rPr is None:
        return

    color = rPr.find(w("color"))
    if color is not None:
        color.set(w("val"), WHITE)
        color.set(w("themeColor"), "background1")
        color.attrib.pop(w("themeShade"), None)
        color.attrib.pop(w("themeTint"), None)

    shd = _ensure_child(rPr, w("shd"))
    shd.set(w("val"), "clear")
    shd.set(w("color"), "auto")
    shd.set(w("fill"), DARKER_NAVY)
    shd.set(w("themeFill"), "text2")


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _ensure_child(parent, tag):
    """Return the first child with *tag*, creating it if absent."""
    child = parent.find(tag)
    if child is None:
        child = etree.SubElement(parent, tag)
    return child


def _serialize(root) -> bytes:
    return etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def apply_fixes(input_path: str, output_path: str) -> None:
    with zipfile.ZipFile(input_path, "r") as zin:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "word/document.xml":
                    data = fix_document(data)
                elif item.filename == "word/styles.xml":
                    data = fix_styles(data)
                zout.writestr(item, data)


def main():
    parser = argparse.ArgumentParser(
        description="Apply accessibility/style fixes to the next_steps instructions docx."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=DEFAULT_INPUT,
        help=f"Input .docx file (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "output",
        nargs="?",
        help="Output .docx file (default: overwrite input in-place)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    output = args.output or args.input

    if output == args.input:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            tmp_path = tmp.name
        try:
            apply_fixes(args.input, tmp_path)
            shutil.move(tmp_path, args.input)
        except Exception:
            os.unlink(tmp_path)
            raise
    else:
        apply_fixes(args.input, output)

    print(f"Done: {output}")


if __name__ == "__main__":
    main()
