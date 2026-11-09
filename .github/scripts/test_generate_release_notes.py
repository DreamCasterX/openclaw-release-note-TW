import base64
import io
import json
import os
import unittest
import urllib.error
from unittest.mock import patch

import generate_release_notes as notes


TAG = "v2026.10.29"
URL = f"https://github.com/openclaw/openclaw/releases/tag/{TAG}"
CHANGELOG_URL = f"https://github.com/openclaw/openclaw/blob/{TAG}/CHANGELOG/{TAG[1:]}.md"
PR_URL = "https://github.com/openclaw/openclaw/pull/123"
RELEASE = {
    "tag_name": TAG, "html_url": URL, "body": "### Changes\nNew feature (#123)",
    "draft": False, "prerelease": False,
}
CHANGELOG = (
    "## Features\n\n"
    f"- Add a concrete capability ([#123]({PR_URL})).\n"
)
REAL_FORMAT_CHANGELOG = """\
## 2026.11.2

### Highlights

- **Privacy and trust boundaries:** Keep diagnostic data protected. (#191318) (#174998)

### Changes

- Optional diagnostic capture bounds oversized payloads.

### Fixes

- **Model routing and providers:** Respect provider settings. (#174156) (#170589)

### Complete contribution record

- **PR #999999** Documentation-only record.
"""
TEXT = (
    f"# OpenClaw {TAG} 版本發佈說明\n\n[GitHub Release]({URL})\n"
    "## 概述\n## 功能更新\n### ⭐ 功能\n"
    "- **用途**: 測試\n- **解決問題**: 測試\n- **影響**: 測試\n"
    "## 安全性提升\n## 錯誤修復\n## 總結\n"
)
LINKED_TEXT = (
    f"# OpenClaw {TAG} 版本發佈說明\n\n[GitHub Release]({URL})\n"
    f"[官方版本變更紀錄]({CHANGELOG_URL})\n"
    "## 概述\n## 功能更新\n"
    f"### ⭐⭐ 新增功能 ([#123]({PR_URL}))\n"
    "- **用途**: 測試\n- **解決問題**: 測試\n- **影響**: 測試\n"
    "## 安全性提升\n本版無相關項目。\n"
    "## 錯誤修復\n本版無相關項目。\n"
    "## 總結\n"
)


class ReleaseNotesTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "GITHUB_REPOSITORY": "example/fork", "GH_TOKEN": "test-token",
            "OPENROUTER_API_KEY": "test-key",
            "RELEASE_TAG": "", "GITHUB_STEP_SUMMARY": "",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_dates_and_revision(self):
        self.assertEqual(notes.release_date("v2026.5.3-1"), "2026-05-03")
        for tag in ("../../bad", "v2026.2.30", "v2026.5.3-beta", "v2026.5.3\n"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                notes.release_date(tag)

    @patch.object(notes, "github")
    def test_load_version_specific_changelog(self, github):
        body = "## Features\n- A sourced feature."
        github.return_value = {
            "path": f"CHANGELOG/{TAG[1:]}.md",
            "encoding": "base64",
            "content": base64.b64encode(body.encode()).decode(),
        }
        result = notes.load_upstream_changelog(TAG)
        self.assertEqual(result, {
            "status": "found", "source_url": CHANGELOG_URL, "content": body,
        })
        self.assertEqual(
            github.call_args.args[0],
            f"openclaw/openclaw/contents/CHANGELOG/{TAG[1:]}.md?ref={TAG}",
        )

    @patch.object(notes, "github")
    def test_load_changelog_rejects_malformed_base64(self, github):
        github.return_value = {
            "path": f"CHANGELOG/{TAG[1:]}.md",
            "encoding": "base64",
            "content": "not-base64!!!",
        }
        with self.assertRaisesRegex(ValueError, "base64-encoded UTF-8"):
            notes.load_upstream_changelog(TAG)

    @patch.object(notes, "github")
    def test_missing_changelog_is_explicit_and_unsafe_tag_is_rejected(self, github):
        github.side_effect = notes.APIError("GitHub", 404)
        self.assertEqual(notes.load_upstream_changelog(TAG), {
            "status": "not_found", "source_url": CHANGELOG_URL, "content": "",
        })
        call_count = github.call_count
        with self.assertRaises(ValueError):
            notes.load_upstream_changelog("../../attacker")
        self.assertEqual(github.call_count, call_count)

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

    def test_sparse_output_rejected_but_empty_categories_are_allowed(self):
        sparse = TEXT.replace(
            f"[GitHub Release]({URL})",
            f"[GitHub Release]({URL})\n[官方版本變更紀錄]({CHANGELOG_URL})",
        ).replace("### ⭐ 功能", "### 本版無功能更新，詳見 changelog")
        with self.assertRaisesRegex(ValueError, "features"):
            notes.validate_notes(
                sparse,
                RELEASE,
                {"status": "found", "source_url": CHANGELOG_URL, "content": CHANGELOG},
            )
        notes.validate_notes(
            LINKED_TEXT,
            RELEASE,
            {"status": "found", "source_url": CHANGELOG_URL, "content": CHANGELOG},
        )
        no_candidates = "## Release notes\nPackaging and verification only."
        empty_text = TEXT.replace(
            f"[GitHub Release]({URL})",
            f"[GitHub Release]({URL})\n[官方版本變更紀錄]({CHANGELOG_URL})",
        )
        notes.validate_notes(
            empty_text,
            RELEASE,
            {"status": "found", "source_url": CHANGELOG_URL, "content": no_candidates},
        )

    def test_real_changelog_headings_and_plain_pr_references(self):
        expected = notes.changelog_candidates(REAL_FORMAT_CHANGELOG)
        self.assertEqual(expected["features"], set())
        self.assertEqual(expected["security"], set())
        self.assertEqual(expected["fixes"], {"174156", "170589"})
        self.assertEqual(expected["unclassified"], {"191318", "174998"})

        text = (
            f"# OpenClaw {TAG} 版本發佈說明\n\n[GitHub Release]({URL})\n"
            f"[官方版本變更紀錄]({CHANGELOG_URL})\n"
            "## 概述\n## 功能更新\n"
            "### ⭐⭐ 隱私與信任邊界 ([#191318](https://github.com/openclaw/openclaw/pull/191318))\n"
            "- **用途**: 測試\n- **解決問題**: 測試\n- **影響**: 測試\n"
            "## 安全性提升\n本版無相關項目。\n"
            "## 錯誤修復\n"
            "### ⭐⭐ 模型路由 ([#174156](https://github.com/openclaw/openclaw/pull/174156))\n"
            "- **用途**: 測試\n- **解決問題**: 測試\n- **影響**: 測試\n"
            "## 總結\n"
        )
        notes.validate_notes(
            text,
            RELEASE,
            {"status": "found", "source_url": CHANGELOG_URL, "content": REAL_FORMAT_CHANGELOG},
        )
        wrong_pr_text = text.replace("/pull/174156", "/pull/999999")
        with self.assertRaisesRegex(ValueError, "fixes"):
            notes.validate_notes(
                wrong_pr_text,
                RELEASE,
                {"status": "found", "source_url": CHANGELOG_URL,
                 "content": REAL_FORMAT_CHANGELOG},
            )

    def test_breaking_changes_require_overview(self):
        with self.assertRaises(ValueError):
            notes.validate_notes(TEXT, {**RELEASE, "body": "## Breaking Changes"})

    @patch.object(notes, "request_json")
    def test_openrouter_request_and_draft_warning(self, request):
        request.return_value = {"choices": [{
            "finish_reason": "stop",
            "message": {"content": TEXT},
        }]}
        result = notes.generate(RELEASE, "guidelines")
        self.assertIn("AI 草稿，待人工審閱", result)
        self.assertEqual(
            request.call_args.args[:3],
            (
                "https://openrouter.ai/api/v1/chat/completions",
                {"Authorization": "Bearer test-key"},
                "POST",
            ),
        )
        self.assertEqual(request.call_args.kwargs["service"], "OpenRouter")
        payload = request.call_args.args[3]
        self.assertEqual(payload["model"], "openrouter/free")
        self.assertEqual([message["role"] for message in payload["messages"]], ["system", "user"])
        self.assertIn("guidelines", payload["messages"][0]["content"])
        self.assertNotIn("test-key", payload["messages"][0]["content"])
        self.assertNotIn("test-key", payload["messages"][1]["content"])
        self.assertEqual(
            json.loads(payload["messages"][1]["content"])["body"],
            RELEASE["body"],
        )

    @patch.object(notes, "request_json")
    def test_prompt_includes_changelog_and_provenance(self, request):
        request.return_value = {"choices": [{
            "finish_reason": "stop",
            "message": {"content": LINKED_TEXT},
        }]}
        source = {
            "status": "found", "source_url": CHANGELOG_URL, "content": CHANGELOG,
        }
        result = notes.generate(RELEASE, "guidelines", source)
        self.assertIn("AI 草稿，待人工審閱", result)
        payload = request.call_args.args[3]
        system_prompt = payload["messages"][0]["content"]
        user_data = json.loads(payload["messages"][1]["content"])
        self.assertIn("synthesize its concrete entries", system_prompt)
        self.assertIn("source code", system_prompt)
        self.assertEqual(user_data["changelog"], CHANGELOG)
        self.assertEqual(user_data["changelog_source_url"], CHANGELOG_URL)
        self.assertEqual(user_data["changelog_status"], "found")

    @patch.object(notes, "request_json")
    def test_generation_rejects_sparse_placeholder_with_available_source(self, request):
        request.return_value = {"choices": [{
            "finish_reason": "stop",
            "message": {"content": TEXT.replace(
                f"[GitHub Release]({URL})",
                f"[GitHub Release]({URL})\n[官方版本變更紀錄]({CHANGELOG_URL})",
            )},
        }]}
        source = {
            "status": "found", "source_url": CHANGELOG_URL, "content": CHANGELOG,
        }
        with self.assertRaisesRegex(ValueError, "features"):
            notes.generate(RELEASE, "guidelines", source)

    @patch.object(notes, "request_json")
    def test_openrouter_response_validation(self, request):
        invalid_results = (
            None,
            {},
            {"choices": []},
            {"choices": [{}]},
            {"choices": [{"message": None}]},
            {"choices": [{"message": {}}]},
            {"choices": [{"message": {"content": "  "}}]},
            {"choices": [{"message": {"content": ["not", "text"]}}]},
            {"choices": [{"message": {"content": TEXT, "refusal": "not allowed"}}]},
            {"choices": [{"finish_reason": "length", "message": {"content": TEXT}}]},
            {"choices": [{"finish_reason": "content_filter", "message": {"content": TEXT}}]},
            {"choices": [{"message": {"content": TEXT}}]},
        )
        for result in invalid_results:
            with self.subTest(result=result):
                request.return_value = result
                with self.assertRaises(ValueError):
                    notes.generate(RELEASE, "guidelines")

    @patch.object(notes.urllib.request, "urlopen")
    def test_request_json_sends_authorization_and_json_body(self, urlopen):
        expected = {"choices": [{"message": {"content": TEXT}}]}
        urlopen.return_value = io.BytesIO(json.dumps(expected).encode())
        payload = {"model": "openrouter/free", "messages": [{"role": "user", "content": "data"}]}
        result = notes.request_json(
            "https://openrouter.ai/api/v1/chat/completions",
            {"Authorization": "Bearer test-key"},
            "POST",
            payload,
            service="OpenRouter",
        )
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(json.loads(request.data), payload)
        self.assertEqual(result, expected)

    def test_missing_secret_and_empty_upstream_fail(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}), self.assertRaisesRegex(
            ValueError, "OPENROUTER_API_KEY"
        ):
            notes.generate(RELEASE, "")
        with self.assertRaises(ValueError):
            notes.generate({**RELEASE, "body": ""}, "")

    @patch.object(notes.urllib.request, "urlopen")
    def test_http_errors_do_not_leak_secrets(self, urlopen):
        urlopen.side_effect = urllib.error.HTTPError(
            "https://openrouter.ai/api?key=test-key", 502, "test-key", {}, None,
        )
        with self.assertRaises(notes.APIError) as caught:
            notes.request_json(
                "https://openrouter.ai/api/v1/chat/completions",
                {"Authorization": "Bearer test-key"},
                method="POST",
                body={"prompt": "private"},
                service="OpenRouter",
            )
        self.assertIn("HTTP 502", str(caught.exception))
        self.assertNotIn("test-key", str(caught.exception))
        self.assertNotIn("private", str(caught.exception))

    @patch.object(notes, "github")
    def test_optional_only_ignores_not_found(self, github):
        github.side_effect = notes.APIError("GitHub", 404)
        self.assertIsNone(notes.optional_github("example/fork"))
        github.side_effect = notes.APIError("GitHub", 403)
        with self.assertRaises(notes.APIError):
            notes.optional_github("example/fork")

    @patch.object(notes, "generate")
    @patch.object(notes, "github")
    def test_recorded_release_does_not_call_openrouter(self, github, generate):
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
            [], notes.APIError("GitHub", 404), notes.APIError("GitHub", 404),
            {"object": {"sha": "base-sha"}},
            {}, notes.APIError("GitHub", 404), {},
            {"html_url": "https://github.com/example/fork/pull/2"},
        ]
        notes.main()
        calls = github.call_args_list
        pr = calls[-1].args[2]
        self.assertTrue(pr["draft"])
        self.assertEqual(pr["base"], "trunk")
        self.assertIn("not found", pr["body"])
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
            [], notes.APIError("GitHub", 404), notes.APIError("GitHub", 404),
            {"object": {"sha": "base-sha"}},
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
            [], notes.APIError("GitHub", 404), {"object": {"sha": "existing-branch"}},
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
            [], notes.APIError("GitHub", 404), notes.APIError("GitHub", 404),
            {"object": {"sha": "base-sha"}},
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
            [], notes.APIError("GitHub", 404), {"object": {"sha": "branch-sha"}},
            notes.APIError("GitHub", 404),
        ]
        with self.assertRaisesRegex(ValueError, "inspect it manually"):
            notes.main()
        generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
