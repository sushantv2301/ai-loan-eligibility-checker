import json
import unittest
import math
from app import app

class TestLoanEligibilityChecker(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_health_endpoint(self):
        resp = self.app.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("claude_integration", data)
        self.assertIn("google_sheets_integration", data)

    def test_calculate_eligibility_prime(self):
        payload = {
            "monthly_income": 10000,
            "existing_debt": 1000,
            "requested_amount": 50000,
            "credit_score": 790,
            "employment_status": "Salaried",
            "loan_purpose": "Home",
            "tenure_years": 5
        }
        resp = self.app.post("/api/calculate-eligibility", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["dti_ratio"], 10.0)
        self.assertGreaterEqual(data["eligibility_score"], 75)
        self.assertIn("Approved", data["approval_verdict"])
        self.assertEqual(data["verdict_badge"], "success")

    def test_calculate_eligibility_high_risk(self):
        payload = {
            "monthly_income": 3000,
            "existing_debt": 2200,
            "requested_amount": 150000,
            "credit_score": 540,
            "employment_status": "Freelancer",
            "loan_purpose": "Personal",
            "tenure_years": 3
        }
        resp = self.app.post("/api/calculate-eligibility", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertGreater(data["dti_ratio"], 50.0)
        self.assertIn("High Risk", data["approval_verdict"])
        self.assertEqual(data["verdict_badge"], "danger")

    def test_calculate_eligibility_invalid_income(self):
        payload = {
            "monthly_income": 0,
            "existing_debt": 500,
            "requested_amount": 25000,
            "credit_score": 700
        }
        resp = self.app.post("/api/calculate-eligibility", json=payload)
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("error", data)

    def test_ai_financial_tips(self):
        telemetry = {
            "monthly_income": 6500,
            "existing_debt": 1500,
            "requested_amount": 35000,
            "credit_score": 720,
            "dti_ratio": 23.08,
            "employment_status": "Salaried",
            "loan_purpose": "Personal",
            "tenure_years": 4,
            "max_eligible_loan": 95000,
            "estimated_emi": 850
        }
        resp = self.app.post("/api/ai/financial-tips", json=telemetry)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("verdict_summary", data)
        self.assertIn("approval_probability", data)
        self.assertIn("key_recommendations", data)
        self.assertIsInstance(data["key_recommendations"], list)
        self.assertGreater(len(data["key_recommendations"]), 0)

    def test_ai_conversational_advisor(self):
        payload = {
            "telemetry": {
                "monthly_income": 8000,
                "existing_debt": 1000,
                "requested_amount": 40000,
                "credit_score": 750,
                "dti_ratio": 12.5
            },
            "question": "How can I negotiate a lower interest rate with lenders?"
        }
        resp = self.app.post("/api/ai/ask", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("answer", data)
        self.assertGreater(len(data["answer"]), 30)

    def test_submissions_persistence_and_retrieval(self):
        record_payload = {
            "applicant_name": "Alexander Hamilton",
            "applicant_email": "alex.hamilton@treasury.gov",
            "monthly_income": 12000,
            "existing_debt": 1500,
            "requested_amount": 60000,
            "employment_status": "Salaried",
            "loan_purpose": "Home",
            "tenure_years": 10,
            "credit_score": 810,
            "dti_ratio": 12.5,
            "calculated_emi": 680.50,
            "max_eligible_loan": 320000,
            "eligibility_score": 94,
            "approval_verdict": "Approved (Prime Tier)"
        }
        save_resp = self.app.post("/api/submissions/save", json=record_payload)
        self.assertEqual(save_resp.status_code, 200)
        save_data = save_resp.get_json()
        self.assertTrue(save_data.get("success"))
        saved_id = save_data["record"]["id"]

        # Now retrieve submissions list
        list_resp = self.app.get("/api/submissions/list")
        self.assertEqual(list_resp.status_code, 200)
        list_data = list_resp.get_json()
        self.assertIn("submissions", list_data)
        ids = [rec["id"] for rec in list_data["submissions"]]
        self.assertIn(saved_id, ids)

    def test_emi_math_precision(self):
        # Benchmark test: ₹1,00,000 principal at 7.5% annual rate for 15 years (180 months)
        # Formula: P * r * (1+r)^n / ((1+r)^n - 1)
        p = 100000.0
        annual_rate = 7.5
        tenure_years = 15
        r = (annual_rate / 100.0) / 12.0
        n = tenure_years * 12
        factor = (1 + r) ** n
        emi = round(p * (r * factor) / (factor - 1), 2)
        # Expected EMI is 927.01
        self.assertAlmostEqual(emi, 927.01, places=1)

    def test_auth_login_demo(self):
        resp = self.app.post("/api/auth/login", json={
            "email": "demo@lendiq.com",
            "password": "demo123"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["user"]["name"], "Sarah Jenkins")
        self.assertIn("token", data)

    def test_auth_register_and_login(self):
        import uuid
        unique_email = f"test_{uuid.uuid4().hex[:6]}@example.com"
        reg_payload = {
            "name": "Kavita Rao",
            "email": unique_email,
            "password": "securepass123",
            "role": "Risk Analyst"
        }
        resp = self.app.post("/api/auth/register", json=reg_payload)
        self.assertIn(resp.status_code, [200, 201])
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["user"]["email"], unique_email)

        # Now test logging in with new user
        login_resp = self.app.post("/api/auth/login", json={
            "email": unique_email,
            "password": "securepass123"
        })
        self.assertEqual(login_resp.status_code, 200)
        login_data = login_resp.get_json()
        self.assertTrue(login_data.get("success"))
        self.assertEqual(login_data["user"]["name"], "Kavita Rao")

    def test_auth_invalid_credentials(self):
        resp = self.app.post("/api/auth/login", json={
            "email": "demo@lendiq.com",
            "password": "wrongpassword"
        })
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertIn("error", data)

if __name__ == "__main__":
    unittest.main()

