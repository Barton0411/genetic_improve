from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.excel_report import data_collectors
from core.excel_report.generator import ExcelReportGenerator


_COLLECTORS = (
    "collect_farm_info",
    "collect_pedigree_data",
    "collect_traits_data",
    "collect_cow_index_data",
    "collect_bull_ranking_data",
    "collect_breeding_genes_data",
    "collect_breeding_inbreeding_data",
    "collect_breeding_detail_data",
    "collect_used_bulls_summary_data",
    "collect_used_bulls_detail_data",
    "collect_candidate_bulls_genes_data",
    "collect_candidate_bulls_inbreeding_data",
    "collect_candidate_bulls_detail_data",
)


class ExcelReportMatingScopeTests(unittest.TestCase):
    def _collect(self, *, include_mating: bool):
        with tempfile.TemporaryDirectory() as temporary_dir:
            generator = ExcelReportGenerator(
                Path(temporary_dir),
                max_workers=1,
                include_mating=include_mating,
            )
            replacements = {
                name: MagicMock(return_value={})
                for name in _COLLECTORS
            }
            mating = MagicMock(return_value={"mating_details": object()})
            replacements["collect_mating_data"] = mating
            with patch.multiple(
                data_collectors,
                **replacements,
            ):
                result = generator._collect_all_data(MagicMock())
        return result, mating

    def test_group_batch_report_does_not_read_existing_mating_results(self):
        result, mating = self._collect(include_mating=False)

        mating.assert_not_called()
        self.assertEqual(result["mating"], {})

    def test_single_farm_report_keeps_existing_mating_section(self):
        result, mating = self._collect(include_mating=True)

        mating.assert_called_once()
        self.assertIn("mating", result)


if __name__ == "__main__":
    unittest.main()
