import base64
import json
import os
import unittest
import urllib.error
from unittest.mock import patch

import generate_release_notes as notes


TAG = "v2026.10.29"
URL = f"https://github.com/openclaw/openclaw/releases/tag/{TAG}"
RELEASE = {
    "tag_name": TAG, "html_url": URL, "body": "### Changes\nNew feature (#123)",
    "draft": False, "prerelease": False,
}
TEXT = (
    f"# OpenClaw {TAG} 版本發佈說明\n\n[GitHub Release]({URL})\n"
    "## 概述\n## 功能更新\n### ⭐ 功能\n"
    "- **用途**: 測試\n- **解決問題**: 測試\n- **影響**: 測試\n"
    "## 安全性提升\n## 錯誤修復\n## 總結\n"
)


class ReleaseNotesTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "GITHUB_REPOSITORY": "example/fork", "GH_TOKEN": "test-token",
            "GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "test-model",
            "RELEASE_TAG": "", "GITHUB_STEP_SUMMARY": "",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_dates_and_revision(self):
        self.assertEqual(notes.release_date("v2026.5.3-1"), "2026-05-03")
        for tag in ("../../bad", "v2026.2.30", "v2026.5.3-beta", "v2026.5.3\n"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                notes.release_date(tag)

    def test_duplicate_url_is_exact(self):
        self.assertTrue(notes.has_release(f"[release]({URL})", URL))
        self.assertFalse(notes.has_release(f"[release]({URL}-1)", URL))
        self.assertFalse(notes.has_release(None, URL))

    def test_validate_rejects_incomplete_notes(self):
        notes.validate_notes(TEXT, RELEASE)
        for text in ("", TEXT.replace(URL, ""), TEXT.replace("## 總結", ""),
                     TEXT + "\n```text\n", TEXT + "\nProduction Ready"):
            with self.subTest(text=text[-40:]), self.assertRaises(ValueError):
                notes.validate_notes(text, RELEASE)

    def test_breaking_changes_require_overview(self):
        with self.assertRaises(ValueError):
            notes.validate_notes(TEXT, {**RELEASE, "body": "## Breaking Changes"})

    @patch.object(notes, "request_json")
    def test_gemini_request_and_draft_warning(self, request):
        request.return_value = {"candidates": [{
            "finishReason": "STOP",
            "content": {"parts": [{"text": TEXT}]},
        }]}
        result = notes.generate(RELEASE, "guidelines")
        self.assertIn("AI 草稿，待人工審閱", result)
        self.assertEqual(request.call_args.args[1], {"x-goog-api-key": "test-key"})
        self.assertNotIn("test-key", request.call_args.args[0])
        payload = request.call_args.args[3]
        self.assertEqual(
            json.loads(payload["contents"][0]["parts"][0]["text"])["body"],
            RELEASE["body"],
        )

    @patch.object(notes, "request_json")
    def test_gemini_truncation_and_safety_block_fail(self, request):
        for result in ({}, {"candidates": [{"finishReason": "MAX_TOKENS"}]}):
            request.return_value = result
            with self.assertRaises(ValueError):
                notes.generate(RELEASE, "")

    def test_missing_secret_and_empty_upstream_fail(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}), self.assertRaises(ValueError):
            notes.generate(RELEASE, "")
        with self.assertRaises(ValueError):
            notes.generate({**RELEASE, "body": ""}, "")

    @patch.object(notes.urllib.request, "urlopen")
    def test_http_errors_do_not_leak_secrets(self, urlopen):
        urlopen.side_effect = urllib.error.HTTPError(
            "https://example.test?key=secret", 403, "secret", {}, None,
        )
        with self.assertRaises(notes.APIError) as caught:
            notes.request_json("https://example.test", {})
        self.assertNotIn("secret", str(caught.exception))

    @patch.object(notes, "github")
    def test_optional_only_ignores_not_found(self, github):
        github.side_effect = notes.APIError("GitHub", 404)
        self.assertIsNone(notes.optional_github("example/fork"))
        github.side_effect = notes.APIError("GitHub", 403)
        with self.assertRaises(notes.APIError):
            notes.optional_github("example/fork")

    @patch.object(notes, "generate")
    @patch.object(notes, "github")
    def test_recorded_release_does_not_call_gemini(self, github, generate):
        github.side_effect = [
            {"default_branch": "main"}, RELEASE,
            {"content": base64.b64encode(TEXT.encode()).decode()},
        ]
        notes.main()
        generate.assert_not_called()
        self.assertEqual(github.call_count, 3)

    @patch.object(notes, "generate")
    @patch.object(notes, "github")
    def test_existing_closed_pr_does_not_regenerate(self, github, generate):
        github.side_effect = [
            {"default_branch": "main"}, RELEASE, notes.APIError("GitHub", 404),
            [{"html_url": "https://github.com/example/fork/pull/1", "state": "closed"}],
        ]
        notes.main()
        generate.assert_not_called()

    @patch.object(notes, "generate", return_value=TEXT)
    @patch.object(notes, "github")
    def test_new_release_creates_draft_on_default_branch(self, github, generate):
        github.side_effect = [
            {"default_branch": "trunk"}, RELEASE, notes.APIError("GitHub", 404),
            [], notes.APIError("GitHub", 404), {"object": {"sha": "base-sha"}},
            {}, notes.APIError("GitHub", 404), {},
            {"html_url": "https://github.com/example/fork/pull/2"},
        ]
        notes.main()
        calls = github.call_args_list
        pr = calls[-1].args[2]
        self.assertTrue(pr["draft"])
        self.assertEqual(pr["base"], "trunk")
        commit = calls[-2].args[2]
        self.assertEqual(base64.b64decode(commit["content"]).decode(), TEXT)
        self.assertNotIn("sha", commit)

    @patch.object(notes, "generate", return_value=TEXT)
    @patch.object(notes, "github")
    def test_same_day_revision_appends_without_overwriting(self, github, generate):
        old = f"Older version\n{URL}-1\n"
        encoded = base64.b64encode(old.encode()).decode()
        github.side_effect = [
            {"default_branch": "main"}, RELEASE, {"content": encoded},
            [], notes.APIError("GitHub", 404), {"object": {"sha": "base-sha"}},
            {}, {"content": encoded, "sha": "file-sha"}, {},
            {"html_url": "https://github.com/example/fork/pull/3"},
        ]
        notes.main()
        commit = github.call_args_list[-2].args[2]
        content = base64.b64decode(commit["content"]).decode()
        self.assertTrue(content.startswith(old.rstrip()))
        self.assertIn(TEXT, content)
        self.assertEqual(commit["sha"], "file-sha")

    @patch.object(notes, "generate")
    @patch.object(notes, "github")
    def test_retry_after_pr_failure_reuses_generated_branch(self, github, generate):
        github.side_effect = [
            {"default_branch": "main"}, RELEASE, notes.APIError("GitHub", 404),
            [], {"object": {"sha": "existing-branch"}},
            {"content": base64.b64encode(TEXT.encode()).decode()},
            {"html_url": "https://github.com/example/fork/pull/4"},
        ]
        notes.main()
        generate.assert_not_called()
        self.assertEqual(github.call_args_list[-1].args[1], "POST")

    @patch.object(notes, "github")
    def test_manual_tag_and_prerelease_rejection(self, github):
        github.side_effect = [{"default_branch": "main"}, {**RELEASE, "prerelease": True}]
        with patch.dict(os.environ, {"RELEASE_TAG": TAG}), self.assertRaises(ValueError):
            notes.main()
        self.assertTrue(github.call_args_list[-1].args[0].endswith(f"tags/{TAG}"))

    @patch.object(notes, "generate", return_value=TEXT)
    @patch.object(notes, "github")
    def test_base_change_during_generation_does_not_overwrite(self, github, generate):
        github.side_effect = [
            {"default_branch": "main"}, RELEASE, notes.APIError("GitHub", 404),
            [], notes.APIError("GitHub", 404), {"object": {"sha": "base-sha"}},
            {}, {"content": base64.b64encode(b"concurrent change").decode(), "sha": "new"},
        ]
        with self.assertRaisesRegex(ValueError, "changed during generation"):
            notes.main()
        self.assertFalse(any("/pulls" == call.args[0][-6:] and len(call.args) > 1
                             for call in github.call_args_list))
        self.assertFalse(any(len(call.args) > 1 and call.args[1] == "PUT"
                             for call in github.call_args_list))

    @patch.object(notes, "generate")
    @patch.object(notes, "github")
    def test_incomplete_branch_is_not_silently_overwritten(self, github, generate):
        github.side_effect = [
            {"default_branch": "main"}, RELEASE, notes.APIError("GitHub", 404),
            [], {"object": {"sha": "branch-sha"}}, notes.APIError("GitHub", 404),
        ]
        with self.assertRaisesRegex(ValueError, "inspect it manually"):
            notes.main()
        generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
