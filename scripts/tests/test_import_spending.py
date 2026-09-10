import unittest
from decimal import Decimal
from scripts import import_spending as m

class ImportSafetyTests(unittest.TestCase):
    def tx(self, **kw):
        t=dict(source='MP card', merchant='Example Shop', merchant_norm='Example Shop', date='2026-06-04', report_month='2026-06', original_amount_brl=Decimal('78.25'), reference='', source_reference='export1')
        t.update(kw)
        return t
    def row(self, t):
        return dict(t, _fingerprint=m.fingerprint(t), included_amount_brl='78.25', category='PERSONAL')
    def test_different_dates_are_distinct(self):
        self.assertFalse(m.ledger_row_matches_raw(self.tx(date='2026-06-05'),self.row(self.tx())))
    def test_installments_in_different_invoices_are_distinct(self):
        self.assertFalse(m.ledger_row_matches_raw(self.tx(report_month='2026-07'),self.row(self.tx())))
    def test_distinct_bank_references(self):
        self.assertFalse(m.ledger_row_matches_raw(self.tx(source='BB',reference='222'),self.row(self.tx(source='BB',reference='111'))))
    def test_cent_difference_is_not_duplicate(self):
        self.assertFalse(m.ledger_row_matches_raw(self.tx(original_amount_brl=Decimal('78.26')),self.row(self.tx())))
    def test_repeated_charges_preserved(self):
        self.assertEqual(len(m.unique_raw_occurrences([self.tx() for _ in range(3)])),3)
    def test_export_overlap_preserves_max_multiplicity(self):
        a=[self.tx() for _ in range(2)]+[self.tx(source_reference='export2') for _ in range(3)]
        self.assertEqual(len(m.unique_raw_occurrences(a)),3)
    def test_redacted_does_not_inherit_without_reference(self):
        t=self.tx(merchant='[REDACTED]',merchant_norm='[REDACTED]')
        self.assertFalse(m.ledger_row_matches_raw(t,self.row(t)))
        for kind in ['exact_recipient','description_contains','identifier_contains']:
            self.assertIsNone(m.match_rule(t,[dict(source='any',match_type=kind,match_value='[REDACTED]')]))
    def test_redacted_exact_reference_can_match(self):
        t=self.tx(merchant='[REDACTED]',merchant_norm='[REDACTED]',reference='1234')
        self.assertTrue(m.ledger_row_matches_raw(t,self.row(t)))
        rule=dict(source='any',match_type='identifier_contains',match_value='1234')
        self.assertEqual(m.match_rule(t,[rule]),rule)
        self.assertIsNone(m.match_rule(t,[dict(rule,match_value='123')]))
    def test_exact_recipient_not_substring(self):
        self.assertIsNone(m.match_rule(self.tx(),[dict(source='any',match_type='exact_recipient',match_value='SHOP')]))
    def test_matching_consumes_each_occurrence_once(self):
        t=self.tx();r=self.row(t);r['_raw_matched']=True
        self.assertIsNone(m.find_matching_ledger_row(t,[r]))
    def test_partial_refund_gross_matches_without_changing_net(self):
        t=self.tx(original_amount_brl=Decimal('200.00'));r=self.row(t);r['included_amount_brl']='199.99'
        self.assertTrue(m.ledger_row_matches_raw(t,r))
        self.assertEqual(r['included_amount_brl'],'199.99')
if __name__=='__main__':unittest.main()
