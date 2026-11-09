"""Diccionario de pronunciación/fonética sustitutiva para VoxForge.

Aplica reescritura fonética práctica ANTES del troceado y del hash de fragmento,
de modo que un término corregido cambia el hash y fuerza regeneración, mientras
los fragmentos no afectados conservan su audio cacheado.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


class PronunciationError(RuntimeError):
    pass


_PREFERRED_DEFAULTS = ("base", "nah", "zh", "en", "hi", "fr", "de")


@dataclass
class PronunciationConfig:
    path: Path | None
    version: int
    default_languages: list[str]
    packs: dict[str, dict[str, str]]
    _cache: dict[tuple[str, ...], tuple[re.Pattern[str] | None, dict[str, str]]] = field(
        default_factory=dict,
        repr=False,
    )

    # Palabras españolas frecuentes que pueden aparecer capitalizadas por inicio
    # de frase. Se usan en minúsculas para comparar de forma normalizada.
    _STARTERS = {
        "el", "la", "los", "las", "un", "una", "unos", "unas",
        "del", "de", "en", "y", "e", "o", "u",
        "que", "quien", "quienes", "como", "cuando", "donde",
        "porque", "pues", "pero", "sino", "ni", "aunque",
        "si", "no", "me", "te", "se", "nos", "os", "le", "les", "lo",
        "mi", "tus", "sus", "nuestro", "nuestra", "vuestro", "vuestra", "su",
        "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas",
        "aquel", "aquella", "todo", "toda", "todos", "todas",
        "cada", "algun", "alguna", "ningun", "ninguna",
        "cierto", "cierta", "otro", "otra", "mismo", "misma",
        "tanto", "tan", "muy", "mas", "más", "apenas",
        "recien", "recién", "ya", "aqui", "aquí", "alli", "allí",
        "ayer", "hoy", "manana", "mañana", "siempre", "nunca",
        "jamas", "jamás", "ahora", "entonces", "luego",
        "despues", "después", "antes", "mientras", "conforme",
        "segun", "según", "con", "sin", "sobre", "tras", "ante",
        "bajo", "cabe", "contra", "desde", "durante", "hacia", "hasta",
        "mediante", "por", "para", "entre", "dijo", "dijeron",
        "asi", "así", "tal", "cual", "cuales", "cuantos", "cuanta", "cuanto",
        "ellos", "ellas", "ello", "nosotros", "nosotras",
        "vosotros", "vosotras", "ustedes", "cuya", "cuyas",
    }

    @classmethod
    def load(cls, path: Path, *, required: bool = False) -> "PronunciationConfig | None":
        if not path.exists():
            if required:
                raise PronunciationError(f"No existe el diccionario: {path}")
            return None

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise PronunciationError(f"JSON inválido en {path}: {exc}") from exc

        if not isinstance(raw, dict):
            raise PronunciationError("El diccionario debe ser un objeto JSON.")

        version = int(raw.get("version", 1))

        default_raw = raw.get("default_languages") or []
        if not isinstance(default_raw, list):
            raise PronunciationError("default_languages debe ser una lista.")
        default_languages = [str(x) for x in default_raw]

        packs_raw = raw.get("packs", {})
        if not isinstance(packs_raw, dict):
            raise PronunciationError("packs debe ser un objeto JSON.")

        packs: dict[str, dict[str, str]] = {}
        for lang, pack in packs_raw.items():
            lang = str(lang)

            if isinstance(pack, dict) and "terms" in pack:
                terms_raw = pack.get("terms", {})
            elif isinstance(pack, dict):
                terms_raw = pack
            else:
                raise PronunciationError(f"Pack '{lang}' inválido.")

            if not isinstance(terms_raw, dict):
                raise PronunciationError(f"Pack '{lang}'.terms debe ser un objeto JSON.")

            terms: dict[str, str] = {}
            for k, v in terms_raw.items():
                if not isinstance(k, str) or not isinstance(v, str):
                    raise PronunciationError(
                        f"Pack '{lang}' tiene pares término/reemplazo no textuales."
                    )
                kk = k.strip()
                vv = v.strip()
                if kk:
                    terms[kk] = vv

            packs[lang] = terms

        if not default_languages:
            default_languages = [x for x in _PREFERRED_DEFAULTS if x in packs]

        unknown = [x for x in default_languages if x not in packs]
        if unknown:
            raise PronunciationError(
                "default_languages refiere packs inexistentes: " + ", ".join(unknown)
            )

        return cls(
            path=path,
            version=version,
            default_languages=default_languages,
            packs=packs,
        )

    def available_languages(self) -> list[str]:
        return list(self.packs.keys())

    def merged_terms(
        self, langs: list[str] | None = None
    ) -> tuple[tuple[str, ...], dict[str, str]]:
        langs_tuple = (
            tuple(self.default_languages)
            if langs is None
            else tuple(str(x) for x in langs)
        )

        missing = [x for x in langs_tuple if x not in self.packs]
        if missing:
            raise PronunciationError(
                "Pack(s) de pronunciación no encontrados: "
                + ", ".join(missing)
                + ". Disponibles: "
                + ", ".join(self.available_languages())
            )

        terms: dict[str, str] = {}
        for lang in langs_tuple:
            terms.update(self.packs[lang])

        return langs_tuple, terms

    def _compiled(
        self, langs: list[str] | None = None
    ) -> tuple[re.Pattern[str] | None, dict[str, str]]:
        langs_tuple, terms = self.merged_terms(langs)

        cached = self._cache.get(langs_tuple)
        if cached is not None:
            return cached

        # Excluimos entradas redundantes (término == reemplazo): no tienen efecto
        # fonético y solo ensuciarían el reporte de check.
        effective = {t: r for t, r in terms.items() if t != r}

        if not effective:
            self._cache[langs_tuple] = (None, {})
            return None, {}

        # Prioriza claves más largas: "New Delhi" gana sobre "Delhi".
        items = sorted(effective.items(), key=lambda kv: len(kv[0]), reverse=True)

        parts: list[str] = []
        lookup: dict[str, str] = {}
        for term, replacement in items:
            if term in lookup:
                continue
            lookup[term] = replacement
            parts.append(r"(?<!\w)" + re.escape(term) + r"(?!\w)")

        pattern = re.compile("|".join(parts), flags=re.UNICODE)
        self._cache[langs_tuple] = (pattern, lookup)
        return pattern, lookup

    def apply(self, text: str, langs: list[str] | None = None) -> str:
        if not text:
            return text

        pattern, lookup = self._compiled(langs)
        if pattern is None:
            return text

        def repl(match: re.Match[str]) -> str:
            return lookup.get(match.group(0), match.group(0))

        return pattern.sub(repl, text)

    def check(self, text: str, langs: list[str] | None = None) -> dict:
        langs_tuple, terms = self.merged_terms(langs)
        pattern, lookup = self._compiled(langs)

        matches: list[dict] = []
        if pattern is not None:
            for m in pattern.finditer(text):
                term = m.group(0)
                matches.append(
                    {
                        "term": term,
                        "replacement": lookup.get(term, ""),
                        "start": m.start(),
                        "end": m.end(),
                    }
                )

        counts_map: dict[str, dict] = {}
        for item in matches:
            term = item["term"]
            if term not in counts_map:
                counts_map[term] = {
                    "term": term,
                    "replacement": item["replacement"],
                    "count": 0,
                }
            counts_map[term]["count"] += 1

        counts = sorted(counts_map.values(), key=lambda x: x["count"], reverse=True)

        # Entradas del diccionario que no hacen nada (término == reemplazo).
        redundant = sorted(t for t, r in terms.items() if t == r)

        return {
            "languages": list(langs_tuple),
            "terms_active": len(terms),
            "terms_effective": len(lookup),
            "matches": matches,
            "counts": counts,
            "redundant": redundant,
            "changed": bool(matches),
        }

    def audit(
        self,
        text: str,
        langs: list[str] | None = None,
        top: int = 80,
        min_len: int = 3,
    ) -> dict:
        """Lista candidatos a diccionario: nombres propios probables, por frecuencia."""
        langs_tuple, terms = self.merged_terms(langs)
        covered = set(terms.keys())

        word_re = re.compile(r"[^\W\d_]+(?:[’'\-][^\W\d_]+)*", re.UNICODE)
        diacritics = set("áéíóúüñàèìòùâêîôûäëïöüçœæ")

        def has_diacritic(word: str) -> bool:
            return any(ch.lower() in diacritics for ch in word)

        counts: dict[str, int] = {}
        for m in word_re.finditer(text):
            w = m.group(0)
            if len(w) < min_len:
                continue
            if not w[0].isupper():
                continue
            counts[w] = counts.get(w, 0) + 1

        def likely_proper(w: str, c: int) -> bool:
            if w.lower() in self._STARTERS:
                return False
            if has_diacritic(w):
                return True
            return c >= 2

        ranked = sorted(
            counts.items(),
            key=lambda kv: (not likely_proper(kv[0], kv[1]), -kv[1], kv[0]),
        )

        all_uncovered: list[dict] = []
        for w, c in ranked:
            if w not in covered and likely_proper(w, c):
                all_uncovered.append({"term": w, "count": c})

        shown: list[dict] = []
        for w, c in ranked[:top]:
            shown.append(
                {
                    "term": w,
                    "count": c,
                    "covered": w in covered,
                    "likely_proper": likely_proper(w, c),
                }
            )

        return {
            "languages": list(langs_tuple),
            "candidates_total": len(counts),
            "shown": len(shown),
            "top": shown,
            "uncovered_total": len(all_uncovered),
            "uncovered_likely": all_uncovered,
        }


def load_pronunciation(path: Path, *, required: bool = False) -> PronunciationConfig | None:
    return PronunciationConfig.load(path, required=required)