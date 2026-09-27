import unittest
from types import SimpleNamespace
from fastapi import HTTPException
from unittest.mock import patch, AsyncMock

from app import payments


class PaymentReconciliationTests(unittest.IsolatedAsyncioTestCase):
    async def test_pro_cannot_create_student_checkout(self):
        current = {"plan": {"id": "pro"}, "subscription": {"expires_at": "2099-10-27T00:00:00+00:00"}}
        with patch.object(payments, "subscription_status", return_value=current), patch.object(payments, "_write_payments") as write, patch.object(payments.httpx, "AsyncClient") as client:
            with self.assertRaises(HTTPException) as error:
                await payments.create_checkout(SimpleNamespace(id="user-1"), "student", "annual", "test@example.com")
            self.assertEqual(error.exception.status_code, 409)
            self.assertIn("27/10/2099", error.exception.detail)
            write.assert_not_called()
            client.assert_not_called()

    def test_other_plan_choices_remain_allowed(self):
        for current, target in (("free", "student"), ("student", "pro"), ("pro", "pro")):
            with self.subTest(current=current, target=target), patch.object(payments, "subscription_status", return_value={"plan": {"id": current}}):
                payments.ensure_checkout_allowed("user-1", target)

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
        with patch.object(payments, "_read_payments", return_value={"payments": {"ORVIX-test": self.record}}), patch.object(payments, "_accept_payment", return_value={**self.record, "status": "ACCEPTED"}) as accept, patch.object(payments, "_send_confirmation", new_callable=AsyncMock) as email:
            result = await payments.apply_geniuspay_webhook(payload)
            self.assertEqual(result["status"], "ACCEPTED")
            accept.assert_called_once()
            email.assert_awaited_once()

    async def test_confirmation_retries_failure_and_skips_sent(self):
        record = {**self.record, "status": "ACCEPTED", "customer_email": "test@example.com"}
        with patch.object(payments, "plans_config", return_value={"plans": []}), patch.object(payments, "_write_payments") as write, patch.object(payments, "send_payment_email", new_callable=AsyncMock, side_effect=[False, True]) as email:
            await payments._send_confirmation(record)
            self.assertNotIn("confirmation_sent_at", record)
            write.assert_not_called()
            await payments._send_confirmation(record)
            self.assertIn("confirmation_sent_at", record)
            await payments._send_confirmation(record)
            self.assertEqual(email.await_count, 2)

    async def test_pending_payment_does_not_send_confirmation(self):
        with patch.object(payments, "send_payment_email", new_callable=AsyncMock) as email:
            await payments._send_confirmation(self.record)
            email.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
