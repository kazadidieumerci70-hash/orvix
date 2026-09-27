import unittest
from unittest.mock import patch

from app import payments


class PaymentReconciliationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.record = {
            "transaction_id": "ORVIX-test",
            "user_id": "user-1",
            "plan_id": "student",
            "billing_cycle": "monthly",
            "amount": 4.99,
            "currency": "USD",
            "status": "PENDING",
            "provider_reference": "MTX-test",
            "created_at": "2026-09-26T01:00:00Z",
        }
        self.confirmation = {
            "reference": "MTX-test",
            "amount": 4.99,
            "currency": "USD",
            "status": "completed",
            "metadata": {"transaction_id": "ORVIX-test", "user_id": "user-1"},
        }

    def test_completed_payment_requires_exact_order_match(self):
        self.assertTrue(payments._payment_matches(self.record, self.confirmation))
        for field, bad_value in (("reference", "MTX-other"), ("amount", 1), ("currency", "XOF")):
            with self.subTest(field=field):
                self.assertFalse(payments._payment_matches(self.record, {**self.confirmation, field: bad_value}))
        self.assertFalse(payments._payment_matches(self.record, {**self.confirmation, "metadata": {"transaction_id": "another", "user_id": "user-1"}}))

    async def test_webhook_activates_only_verified_payment(self):
        payload = {"event": "payment.success", "data": self.confirmation}
        with patch.object(payments, "_read_payments", return_value={"payments": {"ORVIX-test": self.record}}), patch.object(payments, "_accept_payment", return_value={**self.record, "status": "ACCEPTED"}) as accept:
            result = await payments.apply_geniuspay_webhook(payload)
            self.assertEqual(result["status"], "ACCEPTED")
            accept.assert_called_once()


if __name__ == "__main__":
    unittest.main()
