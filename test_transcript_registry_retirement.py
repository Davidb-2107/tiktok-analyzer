import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class TranscriptRegistryRetirementTests(unittest.TestCase):
    def test_analyzer_no_longer_contains_the_legacy_transcript_registry_bridge(self):
        main = (ROOT / "backend/main.py").read_text(encoding="utf-8")
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        frontend = (ROOT / "frontend/src/components/ChannelResults.jsx").read_text(encoding="utf-8")

        self.assertNotIn("transcript_registry", main)
        self.assertNotIn("/save-transcript", main)
        self.assertNotIn("/sourcing/tools", compose)
        self.assertNotIn("save-transcript", frontend)
