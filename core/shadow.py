"""
Shadow Model — Citation Verifier
---------------------------------
Rule-based verifier that checks whether agent output is grounded in its cited sources.

Checks:
  1. Term overlap  — output key terms should appear in the source text
  2. Modality      — "must/shall" in output should not conflict with "may/recommended" in source
  3. PII scan      — output should not contain personal identifiers (presidio-analyzer)
"""

import re
from typing import List

try:
    from presidio_analyzer import AnalyzerEngine as _PresidioEngine
    _presidio = _PresidioEngine()
    _HAS_PRESIDIO = True
except Exception:
    _HAS_PRESIDIO = False

MANDATORY_WORDS = {"must", "shall", "required", "mandatory", "obligatory",
                   "必须", "应当", "须", "不得不"}
ADVISORY_WORDS  = {"should", "recommended", "may", "suggested", "optional",
                   "建议", "可以", "鼓励", "酌情"}

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "of", "in", "on", "at", "to",
    "for", "with", "by", "from", "and", "or", "but", "not", "this", "that",
    "these", "those", "it", "its", "they", "their", "we", "our", "you", "your",
}


def _key_terms(text: str, min_len: int = 4) -> set:
    words = re.findall(r"\b\w+\b", text.lower())
    return {w for w in words if len(w) >= min_len and w not in STOPWORDS}


def _modality(text: str) -> str:
    t = text.lower()
    is_mandatory = any(w in t for w in MANDATORY_WORDS)
    is_advisory  = any(w in t for w in ADVISORY_WORDS)
    if is_mandatory and not is_advisory:
        return "mandatory"
    if is_advisory and not is_mandatory:
        return "advisory"
    return "neutral"


class ShadowVerifier:
    def verify(self, output: str, source_texts: List[str], scan_pii: bool = True) -> dict:
        """
        Returns:
            passed       (bool)  — True if no flags raised
            flags        (list)  — list of issue descriptions
            overlap_score (float) — fraction of output terms found in sources
        """
        flags: List[str] = []

        if not source_texts:
            flags.append("No sources cited — output cannot be verified.")
            return {"passed": False, "flags": flags, "overlap_score": 0.0}

        combined_source = " ".join(source_texts)

        # ── 1. Term overlap ───────────────────────────────────────────────────
        output_terms = _key_terms(output)
        source_terms = _key_terms(combined_source)
        overlap = (
            len(output_terms & source_terms) / len(output_terms)
            if output_terms else 0.0
        )

        if overlap < 0.20:
            flags.append(
                f"Low term overlap ({overlap:.0%}) — output may not be grounded in sources."
            )

        # ── 2. Modality consistency ───────────────────────────────────────────
        out_mod = _modality(output)
        src_mod = _modality(combined_source)

        if out_mod == "mandatory" and src_mod == "advisory":
            flags.append(
                "Modality mismatch: output uses 'must/shall' but source uses 'recommended/may'. "
                "Possible policy hallucination."
            )

        # ── 3. PII scan ───────────────────────────────────────────────────────────
        if _HAS_PRESIDIO and scan_pii:
            pii_results = _presidio.analyze(text=output, language="en")
            # High-risk structured PII → always flag
            HIGH_RISK = {"PHONE_NUMBER", "CREDIT_CARD", "US_SSN",
                         "IBAN_CODE", "MEDICAL_LICENSE", "US_PASSPORT"}
            # Profile-type PII → flag if appears excessively (≥3 = likely a dump)
            PROFILE   = {"PERSON", "EMAIL_ADDRESS", "URL", "LOCATION"}

            for r in pii_results:
                if r.entity_type in HIGH_RISK:
                    flags.append(f"PII in output: {r.entity_type} detected — high-risk identifier")

            soft_hits = [r for r in pii_results if r.entity_type in PROFILE]
            if len(soft_hits) >= 3:
                types = sorted({r.entity_type for r in soft_hits})
                flags.append(
                    f"Excessive personal identifiers in output: {types} "
                    f"({len(soft_hits)} entities) — possible PII exfiltration"
                )

        return {
            "passed": len(flags) == 0,
            "flags": flags,
            "overlap_score": round(overlap, 3),
        }
