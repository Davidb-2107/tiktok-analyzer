import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

import brief_compiler as bc


HEADING = "## Décision — mapping canonique vidéo → sous-formula"
HEADER = (
    "| Video ID | Chaîne | Video style | Realism | Hook mechanic | "
    "Angle / promesse | Progression → payoff | Affectation |"
)
SEPARATOR = "|---|---|---|---:|---|---|---|---|"
_MISSING = object()


def _mapping(rows, *, niche="neon_psycho", heading=HEADING):
    lines = [
        "---",
        f"niche: {niche}",
        "---",
        "",
        heading,
        "",
        HEADER,
        SEPARATOR,
    ]
    lines.extend(
        f"| `{video_id}` | `{channel}` | AI animation | 5 | question | angle | payoff | `{assignment}` |"
        for video_id, channel, assignment in rows
    )
    return "\n".join(lines) + "\n"


def _formula(channel, video_ids, ref="wiki/analyses/mapping.md"):
    return (
        "---\n"
        f"channel: {channel}\n"
        f"subformula_mapping_ref: {ref}\n"
        f"videos: {', '.join(video_ids)}\n"
        "---\n\n"
        f"# CHANNEL FORMULA — {channel}\n"
    )


class SubformulaMappingTests(unittest.TestCase):
    @contextmanager
    def fixture(
        self,
        rows,
        *,
        formula_channel="@alpha",
        formula_ids=("111111111111111111", "222222222222222222"),
        formula_ref="wiki/analyses/mapping.md",
        formula=None,
        mapping=_MISSING,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            formats = root / "Projects" / "Sourcing" / "formats" / "neon_psycho"
            formats.mkdir(parents=True)
            mapping_path = root / "wiki" / "analyses" / "mapping.md"
            mapping_path.parent.mkdir(parents=True)
            if mapping is _MISSING:
                mapping = _mapping(rows)
            if mapping is not None:
                mapping_path.write_text(mapping, encoding="utf-8")
            (formats / f"{formula_channel[1:]}.md").write_text(
                formula
                if formula is not None
                else _formula(formula_channel, formula_ids, formula_ref),
                encoding="utf-8",
            )
            old_formats, old_vault = bc.FORMATS, bc.sc.VAULT
            bc.FORMATS, bc.sc.VAULT = formats.parent, root
            videos = [
                {"niche": "neon_psycho", "channel": formula_channel, "video_id": video_id}
                for video_id in formula_ids
            ]
            try:
                yield videos
            finally:
                bc.FORMATS, bc.sc.VAULT = old_formats, old_vault

    def load(self, rows, **kwargs):
        with self.fixture(rows, **kwargs) as videos:
            return bc.load_subformula_mapping(videos)

    def assert_load_error(self, rows, message, **kwargs):
        with self.fixture(rows, **kwargs) as videos:
            with self.assertRaisesRegex(ValueError, message):
                bc.load_subformula_mapping(videos)

    def route(self, rows, cluster, **kwargs):
        with self.fixture(rows, **kwargs) as videos:
            return bc.route_subformula(videos, cluster)

    def assert_route_error(self, rows, cluster, message, **kwargs):
        with self.fixture(rows, **kwargs) as videos:
            with self.assertRaisesRegex(ValueError, message):
                bc.route_subformula(videos, cluster)

    def test_valid_rows_are_channel_scoped_and_statuses_are_preserved(self):
        rows = [
            ("111111111111111111", "@alpha", "alpha_formula"),
            ("222222222222222222", "@alpha", "alpha_formula"),
            ("333333333333333333", "@beta", "beta_formula"),
            ("444444444444444444", "@beta", "beta_formula"),
        ]
        result = self.load(rows)
        self.assertEqual(
            [(row["video_id"], row["subformula_id"]) for row in result],
            [("111111111111111111", "alpha_formula"), ("222222222222222222", "alpha_formula")],
        )
        self.assertEqual({row["channel"] for row in result}, {"@alpha"})
        self.assertEqual({row["status"] for row in result}, {"assigned"})

    def test_outlier_and_analysis_only_assignments_are_retained(self):
        rows = [
            ("111111111111111111", "@alpha", "alpha_formula"),
            ("222222222222222222", "@alpha", "alpha_formula"),
            ("333333333333333333", "@beta", "beta_analysis*"),
            ("444444444444444444", "@beta", "beta_analysis*"),
            ("555555555555555555", "@beta", "outlier_no_formula"),
        ]
        result = self.load(
            rows,
            formula_channel="@beta",
            formula_ids=(
                "333333333333333333",
                "444444444444444444",
                "555555555555555555",
            ),
        )
        self.assertEqual(
            {row["status"] for row in result},
            {"analysis_group_only", "outlier"},
        )
        self.assertEqual(
            {row["subformula_id"] for row in result},
            {"beta_analysis", "outlier_no_formula"},
        )

        self.assertEqual(result[-1]["status"], "outlier")
        self.assertEqual(result[-1]["subformula_id"], "outlier_no_formula")

    def test_missing_mapping_reference_is_rejected(self):
        formula = "---\nchannel: @alpha\nvideos: 111111111111111111, 222222222222222222\n---\n"
        self.assert_load_error([], "subformula_mapping_ref", formula=formula, mapping=None)

    def test_missing_mapping_file_is_rejected(self):
        self.assert_load_error([], "mapping.*introuvable|mapping.*missing", mapping=None)

    def test_missing_exact_table_is_rejected(self):
        self.assert_load_error(
            [],
            "table.*mapping|mapping.*table",
            mapping="---\nniche: neon_psycho\n---\n\n## Other\n| not the approved table |\n",
        )

    def test_malformed_row_is_rejected(self):
        mapping = _mapping([
            ("111111111111111111", "@alpha", "alpha_formula"),
        ]).replace(
            "| `111111111111111111` | `@alpha` | AI animation | 5 | question | angle | payoff | `alpha_formula` |",
            "| `111111111111111111` | `@alpha` | AI animation | 5 | question | angle | payoff |",
        )
        self.assert_load_error(
            [],
            "malformed|malformée|columns|cell",
            mapping=mapping,
        )

    def test_duplicate_video_id_is_rejected(self):
        self.assert_load_error(
            [
                ("111111111111111111", "@alpha", "alpha_formula"),
                ("111111111111111111", "@alpha", "alpha_formula"),
                ("222222222222222222", "@alpha", "alpha_formula"),
            ],
            "duplicate|dupliqué|unique",
        )

    def test_cross_channel_video_id_is_rejected(self):
        self.assert_load_error(
            [
                ("111111111111111111", "@alpha", "alpha_formula"),
                ("111111111111111111", "@beta", "beta_formula"),
                ("222222222222222222", "@alpha", "alpha_formula"),
            ],
            "cross.channel|multi.channel|plusieurs chaînes|disjoint",
        )

    def test_noncanonical_channel_is_rejected(self):
        self.assert_load_error(
            [
                ("111111111111111111", "@Alpha", "alpha_formula"),
                ("222222222222222222", "@alpha", "alpha_formula"),
            ],
            "non canonique|canonical",
        )

    def test_unknown_assignment_status_is_rejected(self):
        self.assert_load_error(
            [
                ("111111111111111111", "@alpha", "unknown status"),
                ("222222222222222222", "@alpha", "unknown status"),
            ],
            "status|affectation|assignment",
        )

    def test_missing_selected_video_row_is_rejected(self):
        self.assert_load_error(
            [("111111111111111111", "@alpha", "alpha_formula")],
            "missing|manqu|coverage|couverture",
        )

    def test_selected_formula_cannot_use_the_other_channel_row(self):
        rows = [
            ("111111111111111111", "@alpha", "alpha_formula"),
            ("222222222222222222", "@alpha", "alpha_formula"),
            ("333333333333333333", "@beta", "beta_formula"),
            ("444444444444444444", "@beta", "beta_formula"),
        ]
        self.assert_load_error(
            rows,
            "cross.channel|channel|chaîne",
            formula_channel="@alpha",
            formula_ids=("333333333333333333", "444444444444444444"),
        )

    def test_cluster_routes_each_viraldtoprw_assignment_to_its_exact_videos(self):
        rows = [
            ("7571154788486827295", "@viraldtoprw", "viraldtoprw_end_of_life_attachment"),
            ("7568334048544820510", "@viraldtoprw", "viraldtoprw_end_of_life_attachment"),
            ("7572606346403564831", "@viraldtoprw", "viraldtoprw_behavioral_attachment"),
            ("7570326672780643614", "@viraldtoprw", "viraldtoprw_behavioral_attachment"),
            ("7572554313268989215", "@viraldtoprw", "viraldtoprw_behavioral_attachment"),
            ("7597962877495938326", "@the.wisejourney", "wise_provocative_relationship_claim"),
            ("7604187243971939606", "@the.wisejourney", "wise_provocative_relationship_claim"),
        ]
        formula_ids = tuple(row[0] for row in rows[:5])
        expected = {
            "viraldtoprw_end_of_life_attachment": formula_ids[:2],
            "viraldtoprw_behavioral_attachment": formula_ids[2:],
        }
        for cluster, video_ids in expected.items():
            routed = self.route(
                rows,
                cluster,
                formula_channel="@viraldtoprw",
                formula_ids=formula_ids,
            )
            self.assertEqual(tuple(video["video_id"] for video in routed), video_ids)
            self.assertEqual({video["channel"] for video in routed}, {"@viraldtoprw"})

    def test_cluster_rejects_analysis_only_outlier_and_non_exact_assignments(self):
        rows = [
            ("7597962877495938326", "@the.wisejourney", "wise_provocative_relationship_claim"),
            ("7604187243971939606", "@the.wisejourney", "wise_provocative_relationship_claim"),
            ("7608722463937072407", "@the.wisejourney", "wise_pattern_interrupt_shock*"),
            ("7629453809315499286", "@the.wisejourney", "wise_pattern_interrupt_shock*"),
            ("7589746128195783958", "@the.wisejourney", "outlier_no_formula"),
        ]
        formula_ids = tuple(row[0] for row in rows)
        routed = self.route(
            rows,
            "wise_provocative_relationship_claim",
            formula_channel="@the.wisejourney",
            formula_ids=formula_ids,
        )
        self.assertEqual(
            [video["video_id"] for video in routed],
            ["7597962877495938326", "7604187243971939606"],
        )
        for cluster, message in (
            ("wise_pattern_interrupt_shock", "analysis.group.only"),
            ("outlier_no_formula", "outlier"),
            ("wise_", "unknown|inconnu"),
        ):
            self.assert_route_error(
                rows,
                cluster,
                message,
                formula_channel="@the.wisejourney",
                formula_ids=formula_ids,
            )

    def test_cluster_rejects_partial_and_cross_channel_video_selections(self):
        rows = [
            ("111111111111111111", "@alpha", "alpha_formula"),
            ("222222222222222222", "@alpha", "alpha_formula"),
            ("333333333333333333", "@beta", "beta_formula"),
            ("444444444444444444", "@beta", "beta_formula"),
        ]
        with self.fixture(rows) as videos:
            with self.assertRaisesRegex(ValueError, "unexpected mapping rows"):
                bc.route_subformula(videos[:1], "alpha_formula")
            with self.assertRaisesRegex(ValueError, "exactly one selected channel"):
                bc.route_subformula(
                    videos + [
                        {
                            "niche": "neon_psycho",
                            "channel": "@beta",
                            "video_id": "333333333333333333",
                        }
                    ],
                    "alpha_formula",
                )

    def test_compile_brief_cluster_requires_channel(self):
        with self.assertRaisesRegex(ValueError, "--channel"):
            bc.compile_brief("neon_psycho", cluster="alpha_formula")

    def test_cli_cluster_requires_channel(self):
        result = subprocess.run(
            [sys.executable, "brief_compiler.py", "neon_psycho", "--cluster", "alpha_formula"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("--cluster requires --channel", result.stdout)

    @unittest.skipUnless(
        Path(os.environ.get("VAULT_DIR", ""), "wiki/analyses/2026-09-11-neon-psycho-clusters.md").is_file(),
        "canonical Vault mapping is not configured",
    )
    def test_approved_vault_mapping_resolves_exact_channel_sets(self):
        expected = {
            "@viraldtoprw": {
                "viraldtoprw_end_of_life_attachment": {
                    "7571154788486827295",
                    "7568334048544820510",
                },
                "viraldtoprw_behavioral_attachment": {
                    "7572606346403564831",
                    "7570326672780643614",
                    "7572554313268989215",
                },
            },
            "@the.wisejourney": {
                "wise_provocative_relationship_claim": {
                    "7597962877495938326",
                    "7604187243971939606",
                },
                "wise_pattern_interrupt_shock": {
                    "7608722463937072407",
                    "7629453809315499286",
                },
                "outlier_no_formula": {"7589746128195783958"},
            },
        }
        for channel, assignments in expected.items():
            videos = bc.load_registry("neon_psycho", channel=channel)
            result = bc.load_subformula_mapping(videos)
            actual = {}
            for row in result:
                actual.setdefault(row["subformula_id"], set()).add(row["video_id"])
            self.assertEqual(actual, assignments)


if __name__ == "__main__":
    unittest.main()
