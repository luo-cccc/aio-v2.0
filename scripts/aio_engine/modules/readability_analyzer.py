"""
Readability Analyzer
====================
Pure rule-driven readability scoring for articles.
No LLM dependency. Evaluates Flesch-Kincaid, sentence length,
paragraph length, passive voice density, and complex word ratio.
"""

import re
from typing import List


class ReadabilityAnalyzer:
    """AI readability scorer: analyzes text readability metrics."""

    def analyze(self, text: str, headings: List[dict]) -> dict:
        """
        Analyze text readability and return ModuleResult format.

        Args:
            text: Article body text
            headings: List of {"level": int, "text": str}

        Returns:
            Standard module result dict with readability metrics
        """
        word_count = len(text.split())
        if word_count < 30:
            return {
                "status": "skipped",
                "score": 0,
                "score_details": {"reason": "Text too short for readability analysis"},
                "fallback": False,
                "errors": [],
                "recommended_actions": [],
                "data": {},
            }

        sentences = self._split_sentences(text)
        words = text.split()

        # Flesch Reading Ease
        flesch_re = self._flesch_reading_ease(text, sentences, words)
        flesch_kg = self._flesch_kincaid_grade(text, sentences, words)
        avg_sent_len = len(words) / len(sentences) if sentences else 0
        avg_para_len = self._avg_paragraph_length(text)
        passive_ratio = self._passive_voice_ratio(text, sentences)
        long_sentences = sum(1 for s in sentences if len(s.split()) > 25)
        complex_ratio = self._complex_word_ratio(words)

        # Scoring
        scores = {
            "flesch": self._score_flesch(flesch_re),
            "sentence_length": self._score_sentence_length(avg_sent_len),
            "paragraph_length": self._score_paragraph_length(avg_para_len),
            "passive_voice": self._score_passive_voice(passive_ratio),
            "complex_words": self._score_complex_words(complex_ratio),
        }
        total_score = sum(scores.values())

        score_details = {
            "base_score": total_score,
            "reason": f"Readability score {total_score}/100: Flesch {flesch_re:.1f}, avg sentence {avg_sent_len:.1f} words",
            **scores,
        }

        actions = self._derive_actions(
            total_score, flesch_re, avg_sent_len, passive_ratio, long_sentences
        )

        return {
            "status": "success",
            "score": total_score,
            "score_details": score_details,
            "fallback": False,
            "errors": [],
            "recommended_actions": actions,
            "data": {
                "flesch_reading_ease": round(flesch_re, 1),
                "flesch_kincaid_grade": round(flesch_kg, 1),
                "avg_sentence_length": round(avg_sent_len, 1),
                "avg_paragraph_length": round(avg_para_len, 1),
                "passive_voice_ratio": round(passive_ratio, 3),
                "long_sentences_count": long_sentences,
                "complex_words_ratio": round(complex_ratio, 3),
                "sentence_count": len(sentences),
                "word_count": word_count,
            },
        }

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """Split text into sentences."""
        raw = re.split(r'[.!?]+', text)
        return [s.strip() for s in raw if s.strip()]

    @staticmethod
    def _flesch_reading_ease(text: str, sentences: List[str], words: List[str]) -> float:
        """Calculate Flesch Reading Ease score."""
        if not sentences or not words:
            return 0.0
        total_syllables = sum(ReadabilityAnalyzer._count_syllables(w) for w in words)
        return 206.835 - 1.015 * (len(words) / len(sentences)) - 84.6 * (total_syllables / len(words))

    @staticmethod
    def _flesch_kincaid_grade(text: str, sentences: List[str], words: List[str]) -> float:
        """Calculate Flesch-Kincaid Grade Level."""
        if not sentences or not words:
            return 0.0
        total_syllables = sum(ReadabilityAnalyzer._count_syllables(w) for w in words)
        return 0.39 * (len(words) / len(sentences)) + 11.8 * (total_syllables / len(words)) - 15.59

    @staticmethod
    def _count_syllables(word: str) -> int:
        """Estimate syllable count for a word."""
        word = word.lower().strip(".,!?;:\"'")
        if not word:
            return 0
        # Remove trailing e
        if word.endswith("e"):
            word = word[:-1]
        vowels = "aeiouy"
        count = 0
        prev_was_vowel = False
        for ch in word:
            is_vowel = ch in vowels
            if is_vowel and not prev_was_vowel:
                count += 1
            prev_was_vowel = is_vowel
        if count == 0:
            count = 1
        return count

    @staticmethod
    def _avg_paragraph_length(text: str) -> float:
        """Average sentences per paragraph."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return 0.0
        total_sentences = sum(len(re.split(r'[.!?]+', p)) for p in paragraphs)
        return total_sentences / len(paragraphs)

    @staticmethod
    def _passive_voice_ratio(text: str, sentences: List[str]) -> float:
        """Estimate passive voice ratio."""
        if not sentences:
            return 0.0
        passive_patterns = [
            r'\b(?:is|are|was|were|been|be|being)\s+\w+ed\b',
            r'\b(?:has|have|had)\s+been\s+\w+ed\b',
        ]
        passive_count = 0
        for sentence in sentences:
            for pattern in passive_patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    passive_count += 1
                    break
        return passive_count / len(sentences)

    @staticmethod
    def _complex_word_ratio(words: List[str]) -> float:
        """Ratio of words with 3+ syllables."""
        if not words:
            return 0.0
        complex_count = sum(
            1 for w in words
            if ReadabilityAnalyzer._count_syllables(w) >= 3
        )
        return complex_count / len(words)

    @staticmethod
    def _score_flesch(flesch_re: float) -> int:
        """Score Flesch Reading Ease (target 60-70 = standard)."""
        if 60 <= flesch_re <= 70:
            return 30
        elif 50 <= flesch_re < 60 or 70 < flesch_re <= 80:
            return 22
        elif 40 <= flesch_re < 50 or 80 < flesch_re <= 90:
            return 15
        elif 30 <= flesch_re < 40:
            return 8
        return 4

    @staticmethod
    def _score_sentence_length(avg_len: float) -> int:
        """Score average sentence length (target 15-20 words)."""
        if 15 <= avg_len <= 20:
            return 25
        elif 12 <= avg_len < 15 or 20 < avg_len <= 25:
            return 18
        elif 10 <= avg_len < 12 or 25 < avg_len <= 30:
            return 12
        return 6

    @staticmethod
    def _score_paragraph_length(avg_len: float) -> int:
        """Score average paragraph length (target 3-5 sentences)."""
        if 3 <= avg_len <= 5:
            return 20
        elif 2 <= avg_len < 3 or 5 < avg_len <= 7:
            return 14
        elif 1 <= avg_len < 2:
            return 8
        return 4

    @staticmethod
    def _score_passive_voice(ratio: float) -> int:
        """Score passive voice ratio (target <10%)."""
        if ratio < 0.05:
            return 15
        elif ratio < 0.10:
            return 11
        elif ratio < 0.15:
            return 7
        return 3

    @staticmethod
    def _score_complex_words(ratio: float) -> int:
        """Score complex word density (target <15%)."""
        if ratio < 0.10:
            return 10
        elif ratio < 0.15:
            return 7
        elif ratio < 0.20:
            return 4
        return 2

    @staticmethod
    def _derive_actions(score, flesch_re, avg_sent, passive_ratio, long_count) -> List[dict]:
        actions = []
        if score < 50:
            actions.append({
                "action": "Readability score is low. Consider simplifying vocabulary and shortening sentences.",
                "priority": "high",
                "target_module": "readability_analyzer",
                "params": {"current_score": score},
            })
        if flesch_re < 50:
            actions.append({
                "action": f"Flesch Reading Ease ({flesch_re:.1f}) is difficult. Target 60-70 for standard readability.",
                "priority": "medium",
                "target_module": "readability_analyzer",
                "params": {"flesch_re": flesch_re, "target": "60-70"},
            })
        if avg_sent > 25:
            actions.append({
                "action": f"Average sentence length ({avg_sent:.1f} words) is high. Break into shorter sentences (target 15-20).",
                "priority": "medium",
                "target_module": "readability_analyzer",
                "params": {"avg_sentence_length": avg_sent, "target": "15-20"},
            })
        if long_count > 5:
            actions.append({
                "action": f"Found {long_count} sentences over 25 words. Consider breaking them up.",
                "priority": "medium",
                "target_module": "readability_analyzer",
                "params": {"long_sentences": long_count},
            })
        if passive_ratio > 0.15:
            actions.append({
                "action": f"Passive voice ratio ({passive_ratio:.1%}) is high. Use active voice where possible.",
                "priority": "low",
                "target_module": "readability_analyzer",
                "params": {"passive_ratio": passive_ratio},
            })
        return actions
