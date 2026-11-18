import json
import unittest
from contextlib import nullcontext
from unittest.mock import patch
from urllib.error import HTTPError

from pages import lineup_preview
from services.lineup_ai import LineupAIError, explain_lineup


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class LineupAITests(unittest.TestCase):
    def test_ui_explainer_requires_a_configured_key(self):
        with (
            patch.object(lineup_preview, "ANTHROPIC_API_KEY", ""),
            patch.object(lineup_preview.st, "session_state", {}),
            patch.object(
                lineup_preview.st,
                "expander",
                return_value=nullcontext(),
            ),
            patch.object(lineup_preview.st, "caption"),
            patch.object(lineup_preview.st, "info") as show_info,
            patch.object(lineup_preview.st, "button") as show_button,
            patch.object(lineup_preview, "explain_lineup") as explain,
        ):
            lineup_preview._show_ai_lineup_explanation({"league": "CBS"})

        show_info.assert_called_once()
        show_button.assert_not_called()
        explain.assert_not_called()

    def test_ui_explainer_calls_ai_only_after_button_click(self):
        with (
            patch.object(lineup_preview, "ANTHROPIC_API_KEY", "test-key"),
            patch.object(lineup_preview.st, "session_state", {}),
            patch.object(
                lineup_preview.st,
                "expander",
                return_value=nullcontext(),
            ),
            patch.object(lineup_preview.st, "caption"),
            patch.object(lineup_preview.st, "button", return_value=True),
            patch.object(lineup_preview.st, "write") as show_text,
            patch.object(
                lineup_preview,
                "explain_lineup",
                return_value="Optimizer choices explained.",
            ) as explain,
        ):
            lineup_preview._show_ai_lineup_explanation({
                "league": "CBS",
                "projection_source": "CBS",
            })

        explain.assert_called_once_with({
            "league": "CBS",
            "projection_source": "CBS",
        })
        show_text.assert_called_once_with("Optimizer choices explained.")

    @patch("services.lineup_ai.urlopen")
    def test_sends_optimizer_context_to_anthropic_and_returns_explanation(
        self,
        urlopen,
    ):
        urlopen.return_value = FakeResponse({
            "content": [
                {"type": "text", "text": "The swap improves the projection."},
            ],
        })

        result = explain_lineup(
            {
                "league": "CBS",
                "optimized_lineup": [
                    {"Player": "Player One", "Projection": float("nan")},
                ],
                "uncertainties": ["One projection is missing."],
            },
            api_key="test-key",
            model="test-model",
        )

        self.assertEqual(result, "The swap improves the projection.")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(request.get_header("X-api-key"), "test-key")
        payload = json.loads(request.data)
        self.assertEqual(payload["model"], "test-model")
        self.assertIn(
            '"Projection":null',
            payload["messages"][0]["content"],
        )
        self.assertIn("Do not invent projections", payload["system"])

    def test_requires_anthropic_api_key(self):
        with self.assertRaisesRegex(LineupAIError, "ANTHROPIC_API_KEY"):
            explain_lineup({}, api_key="")

    @patch("services.lineup_ai.urlopen")
    def test_surfaces_anthropic_api_errors(self, urlopen):
        error = HTTPError(
            "https://api.anthropic.com/v1/messages",
            401,
            "Unauthorized",
            {},
            None,
        )
        error.read = lambda: b'{"error":{"message":"Invalid API key"}}'
        urlopen.side_effect = error

        with self.assertRaisesRegex(
            LineupAIError,
            "HTTP 401: Invalid API key",
        ):
            explain_lineup({}, api_key="test-key")

    @patch("services.lineup_ai.urlopen")
    def test_rejects_empty_response(self, urlopen):
        urlopen.return_value = FakeResponse({"content": []})

        with self.assertRaisesRegex(LineupAIError, "returned no text"):
            explain_lineup({}, api_key="test-key")


if __name__ == "__main__":
    unittest.main()
