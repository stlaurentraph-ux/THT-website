import os
import unittest
from unittest.mock import MagicMock, patch

from api.subscribe_service import (
    SubscribeInput,
    build_notion_properties,
    check_rate_limit,
    subscribe,
    validate,
)


class SubscribeValidationTests(unittest.TestCase):
    def test_honeypot_silent_ok(self):
        inp = SubscribeInput("x", "a@b.co", "", "", True, "http://spam", "fr", "1.2.3.4")
        r = validate(inp)
        self.assertTrue(r.ok)

    def test_requires_consent(self):
        inp = SubscribeInput("Jean", "jean@example.com", "", "", False, "", "fr", "1.2.3.4")
        r = validate(inp)
        self.assertFalse(r.ok)
        self.assertEqual(r.code, "consent")

    def test_invalid_email(self):
        inp = SubscribeInput("Jean", "not-an-email", "", "", True, "", "fr", "1.2.3.4")
        r = validate(inp)
        self.assertFalse(r.ok)


class NotionPropertyTests(unittest.TestCase):
    def test_maps_schema_and_notes_missing_selects(self):
        schema = {
            "Name": {"type": "title"},
            "Email": {"type": "email"},
            "Country/City": {"type": "rich_text"},
            "Organisation": {"type": "rich_text"},
            "Source": {"type": "select", "select": {"options": [{"name": "Ouili newsletter list"}]}},
            "Relationship": {"type": "select", "select": {"options": [{"name": "Knows THT (Ouili newsletter)"}]}},
            "Notes": {"type": "rich_text"},
        }
        inp = SubscribeInput("Ouili", "test@example.com", "Paris", "THT", True, "", "fr", "127.0.0.1")
        props = build_notion_properties(schema, inp)
        self.assertIn("Name", props)
        self.assertEqual(props["Email"]["email"], "test@example.com")
        notes = props["Notes"]["rich_text"][0]["text"]["content"]
        self.assertIn("Website newsletter form", notes)


class SubscribeIntegrationTests(unittest.TestCase):
    @patch.dict(os.environ, {"SUBSCRIBE_TEST_MODE": "1"}, clear=False)
    def test_test_mode(self):
        inp = SubscribeInput("Alex", "a@example.com", "", "", True, "", "en", "test-mode-only-ip")
        r = subscribe(inp)
        self.assertTrue(r.ok)

    @patch.dict(
        os.environ,
        {
            "NOTION_TOKEN": "secret",
            "NOTION_DATABASE_ID": "9e4d3dbc496e4074b8dc5975f1fc398d",
            "SUBSCRIBE_TEST_MODE": "",
        },
        clear=False,
    )
    @patch("api.subscribe_service.NotionClient")
    @patch("api.subscribe_service.send_notify_email")
    def test_create_and_notify(self, mock_mail, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client
        mock_client.load_schema.return_value = {
            "Name": {"type": "title"},
            "Email": {"type": "email"},
            "Notes": {"type": "rich_text"},
        }
        mock_client.find_by_email.return_value = False
        os.environ["SMTP_HOST"] = "mail.example.com"
        os.environ["SMTP_FROM"] = "from@example.com"
        os.environ["SMTP_USER"] = "user"
        os.environ["SMTP_PASS"] = "pass"
        os.environ["NOTIFY_TO"] = "notify@example.com"

        inp = SubscribeInput("Marie", "marie@example.com", "Lyon", "", True, "", "fr", "10.0.0.1")
        r = subscribe(inp)
        self.assertTrue(r.ok)
        mock_client.create_contact.assert_called_once()
        mock_mail.assert_called_once()

    @patch.dict(
        os.environ,
        {
            "NOTION_TOKEN": "secret",
            "NOTION_DATABASE_ID": "9e4d3dbc496e4074b8dc5975f1fc398d",
        },
        clear=False,
    )
    @patch("api.subscribe_service.NotionClient")
    def test_duplicate_skips_create(self, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client
        mock_client.load_schema.return_value = {
            "Name": {"type": "title"},
            "Email": {"type": "email"},
        }
        mock_client.find_by_email.return_value = True
        inp = SubscribeInput("Marie", "marie@example.com", "", "", True, "", "fr", "10.0.0.2")
        r = subscribe(inp)
        self.assertTrue(r.ok)
        self.assertTrue(r.duplicate)
        mock_client.create_contact.assert_not_called()


class RateLimitTests(unittest.TestCase):
    def test_rate_limit_blocks(self):
        ip = "test-rate-ip"
        for _ in range(5):
            self.assertTrue(check_rate_limit(ip))
        self.assertFalse(check_rate_limit(ip))


if __name__ == "__main__":
    unittest.main()
