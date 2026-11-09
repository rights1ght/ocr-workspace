"""Санитайзер HTML (OCR/TZ §7.5, SEC-4): input и output."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

ALLOWED_TAGS = {
    "p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "table", "thead",
    "tbody", "tr", "td", "th", "caption", "colgroup", "col", "strong", "em", "b",
    "i", "u", "s", "code", "pre", "blockquote", "a", "img", "figure", "figcaption",
    "hr", "br", "span", "div", "sub", "sup", "math", "mrow", "mi", "mo", "mn",
    "msup", "msub",
}
ALLOWED_ATTRS = {"href", "src", "alt", "title", "colspan", "rowspan", "class"}
ALLOWED_DATA = {"data-src-page", "data-src-block", "data-latex", "data-page-break",
                "data-kind", "data-cs", "data-rs"}


def _cleanattrs(tag):
    for name, value in list(tag.attrs.items()):
        lname = name.lower()
        if lname in ALLOWED_DATA or (lname.startswith("data-") and lname in ALLOWED_DATA) or lname in ALLOWED_ATTRS:
            continue
        if lname == "style":
            if not re.fullmatch(r"text-align:\s*(left|center|right|justify)\s*;?", str(value or ""), re.I):
                del tag.attrs[name]
            continue
        if lname.startswith("on"):
            del tag.attrs[name]
            continue
        del tag.attrs[name]


def sanitize_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for bad in soup(["script", "iframe", "object", "embed", "link", "meta", "style"]):
        bad.decompose()
    for tag in soup.find_all(True):
        if tag.name not in ALLOWED_TAGS:
            tag.unwrap()
            continue
        _cleanattrs(tag)
        if tag.name == "a":
            href = str(tag.get("href", "")).strip()
            if href.lower().startswith("javascript:"):
                del tag["href"]
            elif href.startswith(("http://", "https:", "//")):
                tag["rel"] = "noopener noreferrer"
    return str(soup)
