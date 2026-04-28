import sys
sys.path.insert(0, "scripts")

from aio_engine.modules.readability_analyzer import ReadabilityAnalyzer


def test_readability_basic():
    text = "The quick brown fox jumps over the lazy dog. " * 20
    analyzer = ReadabilityAnalyzer()
    result = analyzer.analyze(text, [])
    assert result["status"] == "success"
    assert "score" in result
    assert "data" in result
    assert "flesch_reading_ease" in result["data"]
    assert "avg_sentence_length" in result["data"]
    assert "passive_voice_ratio" in result["data"]


def test_readability_empty_text():
    analyzer = ReadabilityAnalyzer()
    result = analyzer.analyze("", [])
    assert result["status"] == "skipped"


def test_readability_short_text():
    analyzer = ReadabilityAnalyzer()
    result = analyzer.analyze("Hello world.", [])
    assert result["status"] == "skipped"
