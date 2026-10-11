import unittest
from retrieval import load_example, retrieve, valid_citation


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.corpus = load_example()
        self.contract = self.corpus["contract"]
        self.query = self.corpus["query"]

    def search(self, **options):
        return retrieve(self.corpus, self.query, self.contract, **options)

    def test_similar_text_can_rank_wrong_rider_first_without_scope(self):
        self.assertEqual(self.search(scoped=False, limit=1)["citations"][0]["id"], "other-rider-event")

    def test_scope_keeps_company_product_version_and_rider(self):
        hits = self.search()["citations"]
        self.assertTrue(hits)
        self.assertTrue(all(c["document_id"] == "demo-current" and c["riders"] == ["기본특약"] for c in hits))

    def test_unknown_contract_fields_hold_without_citations(self):
        for key in ("company", "product", "version", "rider"):
            for value in (None, "", " ", "없는 항목", [], True):
                with self.subTest(key=key, value=value):
                    contract = dict(self.contract, **{key: value})
                    result = retrieve(self.corpus, self.query, contract)
                    self.assertEqual(result["status"], "hold")
                    self.assertEqual(result["citations"], [])

    def test_ambiguous_edition_holds(self):
        self.corpus["documents"].append(dict(self.corpus["documents"][0], id="duplicate"))
        self.assertEqual(self.search()["citations"], [])

    def test_bundle_keeps_low_ranked_exclusion(self):
        top = self.search(limit=1)["citations"]
        self.assertNotIn("current-exclusion", [c["id"] for c in top])
        bundle = self.search(bundle=True, limit=1)["citations"]
        self.assertIn("current-exclusion", [c["id"] for c in bundle])
        self.assertEqual(len(bundle), len({c["id"] for c in bundle}))
        self.assertTrue(all(c["document_id"] == "demo-current" and c["riders"] == ["기본특약"] for c in bundle))

    def test_empty_and_unrelated_queries_do_not_attach_bundle(self):
        for query in ("", " ", "별빛 우주선", None):
            with self.subTest(query=query):
                self.assertEqual(retrieve(self.corpus, query, self.contract, bundle=True)["citations"], [])

    def test_mutated_quote_hash_and_offsets_are_rejected(self):
        chunk = self.corpus["chunks"][0]
        self.assertTrue(valid_citation(chunk, self.corpus["documents"]))
        for field, value in (("quote", "생성된 문장"), ("sha256", "0" * 64), ("start", -1), ("end", 100000), ("start", True)):
            with self.subTest(field=field):
                self.assertFalse(valid_citation(dict(chunk, **{field: value}), self.corpus["documents"]))

    def test_changed_source_is_not_cited(self):
        self.corpus["documents"][0]["text"] += "수정"
        self.assertEqual(self.search()["citations"], [])

    def test_generation_and_payout_are_not_returned(self):
        result = self.search()
        self.assertFalse(result["generation_used"])
        self.assertEqual(set(result), {"status", "generation_used", "citations"})

    def test_invalid_limits_rejected(self):
        for limit in (0, -1, True, 1.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.search(limit=limit)


if __name__ == "__main__":
    unittest.main()
