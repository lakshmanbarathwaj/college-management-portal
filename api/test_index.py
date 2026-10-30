import unittest

from api.index import app


class FlaskAppTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_homepage_renders_flask_template(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"College Assistant", response.data)
        self.assertIn(b"/static/accounts/styles.css", response.data)
        response.close()

    def test_static_files_are_served_from_existing_static_folder(self):
        response = self.client.get("/static/accounts/styles.css")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b".portal-home", response.data)
        response.close()

    def test_question_uses_static_knowledge_file(self):
        response = self.client.post(
            "/api/answer",
            json={"question": "What is the fee structure?"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Term fee - 10000", response.json["answer"])

    def test_invalid_question_returns_a_client_error(self):
        response = self.client.post("/api/answer", json={"question": " "})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "ok")


if __name__ == "__main__":
    unittest.main()
