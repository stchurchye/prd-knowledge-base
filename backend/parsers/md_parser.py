"""Markdown file parser — extracts sections by headings."""

import re


def parse_markdown(filepath: str) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        raw_text = f.read()

    lines = raw_text.split("\n")
    title = ""
    sections = []
    current_heading = ""
    current_lines: list[str] = []

    for line in lines:
        heading_match = re.match(r"^(#{1,3})\s+(.+)", line)
        if heading_match:
            # Save previous section
            if current_heading and current_lines:
                body = "\n".join(current_lines).strip()
                if body:
                    sections.append({"heading": current_heading, "content": body})
            current_heading = heading_match.group(2).strip()
            current_lines = []
            if not title:
                title = current_heading
        else:
            current_lines.append(line)

    # Last section
    if current_heading and current_lines:
        body = "\n".join(current_lines).strip()
        if body:
            sections.append({"heading": current_heading, "content": body})

    # If no headings found, treat entire file as one section
    if not sections and raw_text.strip():
        sections.append({"heading": title or "全文", "content": raw_text.strip()})

    return {
        "title": title,
        "raw_text": raw_text,
        "sections": sections,
    }
