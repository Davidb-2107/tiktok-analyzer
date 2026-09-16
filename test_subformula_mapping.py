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
    for row in rows:
        if len(row) == 3:
            video_id, channel, assignment = row
            style, realism, hook = "AI animation", 5, "question"
        else:
            video_id, channel, assignment, style, realism, hook = row
        lines.append(
            "| `{video_id}` | `{channel}` | {style} | {realism} | {hook} | angle | payoff | `{assignment}` |".format(
                video_id=video_id,
                channel=channel,
                style=style,
                realism=realism,
                hook=hook,
                assignment=assignment,
            )
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

    def test_shared_visual_values_never_merge_channel_formulas(self):
        rows = [
            ("111111111111111111", "@alpha", "alpha_formula", "AI animation", 5, "question"),
            ("222222222222222222", "@alpha", "alpha_formula", "AI animation", 5, "question"),
            ("333333333333333333", "@beta", "beta_formula", "AI animation", 5, "question"),
            ("444444444444444444", "@beta", "beta_formula", "AI animation", 5, "question"),
        ]
        alpha_ids = ("111111111111111111", "222222222222222222")
        beta_ids = ("333333333333333333", "444444444444444444")

        self.assertEqual(
            [video["video_id"] for video in self.route(rows, "alpha_formula")],
            list(alpha_ids),
        )
        self.assertEqual(
            [
                video["video_id"]
                for video in self.route(
                    rows,
                    "beta_formula",
                    formula_channel="@beta",
                    formula_ids=beta_ids,
                )
            ],
            list(beta_ids),
        )

    def test_two_channel_fixture_routes_exact_sets_and_preserves_outlier(self):
        rows = [
            ("111111111111111111", "@alpha", "alpha_formula", "AI animation", 5, "question"),
            ("222222222222222222", "@alpha", "alpha_formula", "AI animation", 5, "question"),
            ("333333333333333333", "@beta", "beta_formula", "POV skit", 2, "bold claim"),
            ("444444444444444444", "@beta", "beta_formula", "POV skit", 2, "bold claim"),
            ("555555555555555555", "@beta", "outlier_no_formula", "POV skit", 2, "bold claim"),
        ]
        beta_ids = ("333333333333333333", "444444444444444444", "555555555555555555")

        self.assertEqual(
            [video["video_id"] for video in self.route(rows, "alpha_formula")],
            ["111111111111111111", "222222222222222222"],
        )
        self.assertEqual(
            [
                video["video_id"]
                for video in self.route(
                    rows,
                    "beta_formula",
                    formula_channel="@beta",
                    formula_ids=beta_ids,
                )
            ],
            ["333333333333333333", "444444444444444444"],
        )
        self.assert_route_error(
            rows,
            "outlier_no_formula",
            "outlier",
            formula_channel="@beta",
            formula_ids=beta_ids,
        )

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

    def test_mapping_reference_cannot_escape_the_vault(self):
        self.assert_load_error([], "escapes configured Vault", formula_ref="../mapping.md")

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

    def test_cluster_rejects_mixed_status_assignment_as_ambiguous(self):
        rows = [
            ("111111111111111111", "@alpha", "alpha_formula"),
            ("222222222222222222", "@alpha", "alpha_formula*"),
        ]
        self.assert_route_error(rows, "alpha_formula", "ambiguous")

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

    def test_approved_vault_mapping_resolves_exact_channel_sets(self):
        vault_dir = os.environ.get("VAULT_DIR")
        self.assertTrue(
            vault_dir,
            "release gate requires VAULT_DIR pointing at the canonical Vault; "
            "the real mapping check must not be skipped",
        )
        mapping_path = Path(vault_dir) / "wiki/analyses/2026-09-11-neon-psycho-clusters.md"
        self.assertTrue(
            mapping_path.is_file(),
            "release gate requires the canonical mapping at "
            f"{mapping_path}",
        )
        expected = {
            "@viraldtoprw": {
                "viraldtoprw_end_of_life_attachment": (
                    {"7571154788486827295", "7568334048544820510"}, "assigned"
                ),
                "viraldtoprw_behavioral_attachment": (
                    {
                        "7572606346403564831",
                        "7570326672780643614",
                        "7572554313268989215",
                    },
                    "assigned",
                ),
            },
            "@the.wisejourney": {
                "wise_provocative_relationship_claim": (
                    {"7597962877495938326", "7604187243971939606"}, "assigned"
                ),
                "wise_pattern_interrupt_shock": (
                    {"7608722463937072407", "7629453809315499286"},
                    "analysis_group_only",
                ),
                "outlier_no_formula": ({"7589746128195783958"}, "outlier"),
            },
        }
        for channel, assignments in expected.items():
            videos = bc.load_registry("neon_psycho", channel=channel)
            result = bc.load_subformula_mapping(videos)
            actual = {}
            for row in result:
                ids, statuses = actual.setdefault(row["subformula_id"], (set(), set()))
                ids.add(row["video_id"])
                statuses.add(row["status"])
            self.assertTrue(
                all(len(statuses) == 1 for _ids, statuses in actual.values()),
                f"non-uniform mapping statuses: {actual}",
            )
            actual = {
                subformula_id: (ids, status.pop())
                for subformula_id, (ids, status) in actual.items()
            }
            self.assertEqual(actual, assignments)

            cluster = next(
                subformula_id
                for subformula_id, (_ids, status) in assignments.items()
                if status == "assigned"
            )
            brief = bc.compile_brief("neon_psycho", channel=channel, cluster=cluster)
            slug = channel[1:]
            self.assertEqual(brief["source"]["channel"], channel)
            self.assertEqual(
                brief["source"]["format_card_ref"],
                f"Projects/Sourcing/transcripts/neon_psycho/{slug}/",
            )
            self.assertEqual(
                brief["source"]["channel_formula_ref"],
                f"Projects/Sourcing/formats/neon_psycho/{slug}.md",
            )


if __name__ == "__main__":
    unittest.main()
