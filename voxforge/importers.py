"""Importación de texto: TXT/MD, DOCX, EPUB y PDF (texto embebido u OCR)."""
from __future__ import annotations

import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.parse import unquote

from .ocrclean import clean_ocr_pages


class ImporterError(RuntimeError):
    pass


TEXT_EXTS = {".txt", ".md"}
PDF_EXTS = {".pdf"}
DOCX_EXTS = {".docx"}
EPUB_EXTS = {".epub"}

BINARY_IMPORT_EXTS = PDF_EXTS | DOCX_EXTS | EPUB_EXTS
SUPPORTED_EXTS = TEXT_EXTS | BINARY_IMPORT_EXTS

_MIN_PDF_CHARS = 30
_OCR_DPI = 300
_NBSP = "\xa0"
LogFn = Callable[[str], None] | None

# Códigos de tesseract para los idiomas habituales del proyecto.
_OCR_LANG_MAP = {
    "es": "spa", "spa": "spa",
    "en": "eng", "eng": "eng",
    "pt": "por", "por": "por",
    "fr": "fra", "fra": "fra",
    "de": "deu", "deu": "deu",
    "it": "ita", "ita": "ita",
    "ca": "cat", "cat": "cat",
    "gl": "glg", "glg": "glg",
    "eu": "eus", "eus": "eus",
    "nl": "nld", "nld": "nld",
    "ru": "rus", "rus": "rus",
    "zh": "chi_sim", "zh-cn": "chi_sim", "chi_sim": "chi_sim",
    "zh-tw": "chi_tra", "chi_tra": "chi_tra",
    "ja": "jpn", "jpn": "jpn",
    "ko": "kor", "kor": "kor",
    "ar": "ara", "ara": "ara",
    "hi": "hin", "hin": "hin",
}

_DOCX_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_EPUB_CONTAINER_NS = "{urn:oasis:names:tc:opendocument:xmlns:container}"
_EPUB_OPF_NS = "{http://www.idpf.org/2007/opf}"


def _clean_text(text: str) -> str:
    """Normaliza espacios y saltos de línea sin destruir párrafos."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(_NBSP, " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _open_zip(path: Path, kind: str) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(path, "r")
    except zipfile.BadZipFile as exc:
        raise ImporterError(
            f"El archivo no es un {kind} válido: ZIP dañado o formato incorrecto."
        ) from exc
    except OSError as exc:
        raise ImporterError(f"No se pudo abrir el {kind}: {exc}") from exc


# --------------------------------------------------------------------------- #
# TXT / MD                                                                     #
# --------------------------------------------------------------------------- #

def extract_plain(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ImporterError(f"No se pudo leer el archivo de texto: {exc}") from exc
    return _clean_text(text)


# --------------------------------------------------------------------------- #
# PDF: texto embebido y OCR de escaneos                                        #
# --------------------------------------------------------------------------- #

def _import_pymupdf():
    """Devuelve el módulo PyMuPDF, aceptando el nombre antiguo `fitz`."""
    try:
        import pymupdf  # PyMuPDF >= 1.24
        return pymupdf
    except ImportError:
        try:
            import fitz  # nombre histórico (emite un aviso de deprecación)
            return fitz
        except ImportError as exc:
            raise ImporterError(
                "Falta pymupdf para leer PDF. Instala: uv pip install pymupdf"
            ) from exc


def _tesseract_lang(lang: str | None) -> str:
    """Traduce el idioma del proyecto a un código de tesseract disponible."""
    import pytesseract

    raw = (lang or "spa").strip().lower().replace("_", "-")
    code = _OCR_LANG_MAP.get(raw) or _OCR_LANG_MAP.get(raw.split("-")[0], raw)

    try:
        available = set(pytesseract.get_languages(config=""))
    except Exception:
        return code

    if code in available:
        return code

    for fallback in ("spa", "eng"):
        if fallback in available:
            return fallback

    return code


def _ocr_pdf(path: Path, *, lang: str, min_chars: int, log: LogFn) -> str:
    """Aplica OCR página a página a un PDF escaneado y devuelve el texto."""
    fitz = _import_pymupdf()

    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise ImporterError(
            "Falta pytesseract o Pillow para aplicar OCR a PDF escaneados. "
            "Instala: uv pip install pytesseract pillow"
        ) from exc

    try:
        code = _tesseract_lang(lang)
    except Exception:
        code = _OCR_LANG_MAP.get((lang or "spa").lower(), "spa")

    chunks: list[str] = []
    try:
        with fitz.open(str(path)) as doc:
            total = doc.page_count
            if log:
                log(
                    f"PDF sin texto embebido: aplicando OCR a {total} páginas "
                    f"(idioma '{code}', {_OCR_DPI} dpi)..."
                )
            for i, page in enumerate(doc, start=1):
                pix = page.get_pixmap(dpi=_OCR_DPI, alpha=False)
                image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                text = pytesseract.image_to_string(image, lang=code)
                # Se conserva una entrada por página (aunque esté vacía) para
                # que la limpieza pueda emparejar folios con el índice del PDF.
                chunks.append(text)
                if log and (i % 10 == 0 or i == total):
                    log(f"  OCR {i}/{total} páginas")
    except ImporterError:
        raise
    except pytesseract.TesseractNotFoundError as exc:
        raise ImporterError(
            "No se encontró el programa tesseract. Instálalo con: "
            "sudo apt install tesseract-ocr tesseract-ocr-spa"
        ) from exc
    except pytesseract.TesseractError as exc:
        raise ImporterError(
            "tesseract no pudo reconocer el PDF. Comprueba que el paquete de "
            f"idioma '{code}' esté instalado. Detalle: {exc}"
        ) from exc
    except Exception as exc:
        raise ImporterError(f"El OCR del PDF falló: {exc}") from exc

    cleaned = clean_ocr_pages(chunks)
    text = _clean_text(cleaned.text)

    if log:
        details = []
        if cleaned.hyphen_joins:
            details.append(f"{cleaned.hyphen_joins} palabras unidas por guion")
        if cleaned.page_numbers_removed:
            details.append(f"{cleaned.page_numbers_removed} folios eliminados")
        if cleaned.headers_removed:
            details.append(f"{cleaned.headers_removed} encabezados repetidos")
        if cleaned.noise_lines_removed:
            details.append(f"{cleaned.noise_lines_removed} líneas de ruido")
        if details:
            log("  Limpieza OCR: " + ", ".join(details) + ".")

    if len(text) < min_chars:
        raise ImporterError(
            "El PDF parece escaneado y el OCR no extrajo texto suficiente. "
            "Comprueba que tesseract y su paquete de idioma estén instalados "
            "(por ejemplo: tesseract-ocr-spa)."
        )

    return text


def extract_pdf(
    path: Path,
    min_chars: int = _MIN_PDF_CHARS,
    *,
    lang: str = "spa",
    ocr: bool = True,
    log: LogFn = None,
) -> str:
    """Extrae el texto de un PDF.

    Primero usa el texto embebido. Si no llega a `min_chars`, aplica OCR con
    tesseract (desactivable con `ocr=False`) y devuelve el texto reconocido.
    """
    fitz = _import_pymupdf()

    try:
        with fitz.open(str(path)) as doc:
            if doc.needs_pass:
                raise ImporterError(
                    "El PDF está protegido con contraseña; quita la protección antes de importarlo."
                )
            pages = [page.get_text("text") for page in doc]
            text = _clean_text("\n\n".join(p for p in pages if p))
    except ImporterError:
        raise
    except Exception as exc:
        raise ImporterError(f"No se pudo leer el PDF: {exc}") from exc

    if len(text) >= min_chars:
        return text

    if not ocr:
        raise ImporterError(
            "El PDF no tiene suficiente texto embebido; parece escaneado. "
            "Vuelve a intentarlo con el OCR activado."
        )

    return _ocr_pdf(path, lang=lang, min_chars=min_chars, log=log)


# --------------------------------------------------------------------------- #
# DOCX                                                                         #
# --------------------------------------------------------------------------- #

def _docx_paragraph_text(paragraph: ET.Element) -> str:
    """Extrae texto de un párrafo DOCX, incluyendo tabs y saltos simples."""
    parts: list[str] = []

    for node in paragraph.iter():
        tag = node.tag

        if tag == _DOCX_W + "t":
            parts.append(node.text or "")
        elif tag == _DOCX_W + "tab":
            parts.append(" ")
        elif tag == _DOCX_W + "br":
            parts.append("\n")

    text = "".join(parts)
    return re.sub(r"\s+", " ", text).strip()


def extract_docx(path: Path) -> str:
    """Extrae texto del cuerpo principal de un DOCX.

    Limitaciones deliberadas v1:
    - Lee word/document.xml.
    - Incluye párrafos dentro de tablas.
    - No lee encabezados, pies de página, notas al pie, comentarios ni cuadros de texto.
    """
    try:
        with _open_zip(path, "DOCX") as z:
            try:
                data = z.read("word/document.xml")
            except KeyError as exc:
                raise ImporterError(
                    "El DOCX no contiene word/document.xml; podría estar dañado "
                    "o usar una estructura no soportada."
                ) from exc

            try:
                root = ET.fromstring(data)
            except ET.ParseError as exc:
                raise ImporterError(f"XML inválido en word/document.xml: {exc}") from exc

            paragraphs: list[str] = []

            for p in root.iter(_DOCX_W + "p"):
                txt = _docx_paragraph_text(p)
                if txt:
                    paragraphs.append(txt)

            text = "\n\n".join(paragraphs)

    except ImporterError:
        raise
    except Exception as exc:
        raise ImporterError(f"No se pudo leer el DOCX: {exc}") from exc

    text = _clean_text(text)

    if not text:
        raise ImporterError("El DOCX no contiene texto extraíble.")

    return text


# --------------------------------------------------------------------------- #
# EPUB                                                                         #
# --------------------------------------------------------------------------- #

class _HTMLTextExtractor(HTMLParser):
    """Extracts readable text from XHTML/HTML, skipping metadata and scripts."""

    SKIP_TAGS = {
        "script",
        "style",
        "head",
        "title",
        "template",
        "noscript",
    }

    BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "figure",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()

        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return

        if self._skip_depth:
            return

        if tag == "br":
            self.parts.append("\n")
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if tag in self.SKIP_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return

        if self._skip_depth:
            return

        if tag in self.BLOCK_TAGS:
            self.parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data:
            self.parts.append(data)


def _html_to_text(data: bytes) -> str:
    html = data.decode("utf-8-sig", errors="replace")
    parser = _HTMLTextExtractor()
    parser.feed(html)
    parser.close()
    return _clean_text("".join(parser.parts))


def _epub_opf_path(z: zipfile.ZipFile) -> str:
    try:
        container = z.read("META-INF/container.xml")
    except KeyError:
        candidates = [n for n in z.namelist() if n.lower().endswith(".opf")]
        if not candidates:
            raise ImporterError(
                "El EPUB no tiene META-INF/container.xml ni ningún archivo .opf."
            )
        return candidates[0].lstrip("/")

    try:
        root = ET.fromstring(container)
    except ET.ParseError as exc:
        raise ImporterError(f"META-INF/container.xml inválido: {exc}") from exc

    rootfile = root.find(f".//{_EPUB_CONTAINER_NS}rootfile")

    if rootfile is None:
        candidates = [n for n in z.namelist() if n.lower().endswith(".opf")]
        if not candidates:
            raise ImporterError("El EPUB no declara un archivo OPF válido.")
        return candidates[0].lstrip("/")

    path = rootfile.attrib.get("full-path")

    if not path:
        raise ImporterError("El container.xml del EPUB no tiene full-path en rootfile.")

    return path.lstrip("/")


def _epub_manifest_spine(opf_data: bytes) -> tuple[dict[str, tuple[str, str]], list[str]]:
    try:
        root = ET.fromstring(opf_data)
    except ET.ParseError as exc:
        raise ImporterError(f"El OPF del EPUB no es XML válido: {exc}") from exc

    items: dict[str, tuple[str, str]] = {}

    for item in root.iter(_EPUB_OPF_NS + "item"):
        item_id = item.attrib.get("id")
        href = item.attrib.get("href")
        media_type = item.attrib.get("media-type", "")

        if item_id and href:
            items[item_id] = (href, media_type)

    spine: list[str] = []

    for itemref in root.iter(_EPUB_OPF_NS + "itemref"):
        idref = itemref.attrib.get("idref")
        if idref:
            spine.append(idref)

    return items, spine


def _epub_resolve(opf_dir: str, href: str) -> str:
    href = unquote(href.split("#", 1)[0].split("?", 1)[0])

    if not href:
        return ""

    path = posixpath.normpath(posixpath.join(opf_dir, href))

    if path.startswith("../"):
        raise ImporterError(f"El EPUB referencia una ruta fuera del paquete: {href!r}")

    return path.lstrip("/")


def _epub_should_parse(media_type: str, member: str) -> bool:
    mt = (media_type or "").lower()

    if mt.startswith(("image/", "font/", "audio/", "video/")):
        return False

    if mt in {
        "text/css",
        "application/javascript",
        "text/javascript",
        "application/x-font-ttf",
    }:
        return False

    suffix = posixpath.splitext(member)[1].lower()

    if suffix in {".html", ".htm", ".xhtml"}:
        return True

    if suffix == ".xml":
        return "html" in mt or "xhtml" in mt

    return "html" in mt


def extract_epub(path: Path) -> str:
    """Extrae texto de un EPUB siguiendo el orden del spine.

    Limitaciones deliberadas v1:
    - No soporta EPUB cifrados/DRM.
    - Ignora imágenes, CSS, JS, fuentes y metadatos HTML.
    - Usa el orden declared en <spine>.
    """
    try:
        with _open_zip(path, "EPUB") as z:
            opf_path = _epub_opf_path(z)
            opf_dir = posixpath.dirname(opf_path)

            try:
                opf_data = z.read(opf_path)
            except KeyError as exc:
                raise ImporterError(f"El EPUB no contiene el OPF declarado: {opf_path}") from exc

            items, spine = _epub_manifest_spine(opf_data)

            if not spine:
                raise ImporterError("El EPUB no tiene spine; no se puede ordenar el texto.")

            chunks: list[str] = []

            for idref in spine:
                item = items.get(idref)

                if not item:
                    continue

                href, media_type = item
                member = _epub_resolve(opf_dir, href)

                if not member:
                    continue

                if not _epub_should_parse(media_type, member):
                    continue

                try:
                    data = z.read(member)
                except KeyError:
                    # Algunos EPUB generan rutas ligeramente distintas; ignoramos
                    # el elemento si no está, pero seguimos con el resto.
                    continue

                text = _html_to_text(data)

                if text:
                    chunks.append(text)

            full_text = "\n\n".join(chunks)

    except ImporterError:
        raise
    except Exception as exc:
        raise ImporterError(f"No se pudo leer el EPUB: {exc}") from exc

    full_text = _clean_text(full_text)

    if not full_text:
        raise ImporterError("El EPUB no contiene texto extraíble en el spine.")

    return full_text


# --------------------------------------------------------------------------- #
# API pública                                                                  #
# --------------------------------------------------------------------------- #

def extract_text(
    path: Path,
    lang: str = "spa",
    *,
    ocr: bool = True,
    log: LogFn = None,
) -> str:
    """Extrae texto de TXT, MD, DOCX, EPUB o PDF.

    En PDF usa primero el texto embebido y, si no hay, OCR con tesseract.
    `lang` es el idioma del OCR (código ISO o de tesseract: es/spa, en/eng...).
    """
    if not path.is_file():
        raise ImporterError(f"No existe el archivo: {path}")

    ext = path.suffix.lower()

    if ext in TEXT_EXTS or ext == "":
        text = extract_plain(path)
    elif ext in PDF_EXTS:
        text = extract_pdf(path, lang=lang, ocr=ocr, log=log)
    elif ext in DOCX_EXTS:
        text = extract_docx(path)
    elif ext in EPUB_EXTS:
        text = extract_epub(path)
    else:
        raise ImporterError(
            f"Formato no soportado: {ext or '(sin extensión)'}. "
            "Usa TXT, MD, DOCX, EPUB o PDF."
        )

    if not text.strip():
        raise ImporterError("No se pudo extraer texto (documento vacío).")

    return text