import unittest
from evidence.check_record import check


class EvidenceTests(unittest.TestCase):
    def test_historical_totals_and_image_hashes(self):
        self.assertEqual(check(), {"A_raw": "3/18", "B_scoped": "18/18",
                                  "C_scoped_ontology": "18/18", "D_existing_bundle": "18/18",
                                  "E_dense_raw": "4/18", "F_dense_scoped": "17/18"})
