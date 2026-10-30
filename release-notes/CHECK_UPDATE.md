# OpenClaw Release Notes 自動更新

此獨立 repo 使用 GitHub Actions + Google Gemini API，直接追蹤
`openclaw/openclaw` 官方發布。

```text
每日排程 / 手動執行
        |
        v
取得官方最新正式 Release（或指定 tag）
        |
        v
檢查預設分支已收錄版本 / 同版本既有 PR
        |
        v
Gemini 依 GUIDELINES.md 產生繁中草稿
        |
        v
基本格式檢查 -> 專用分支 -> Draft PR
        |
        v
人工核對、補齊原始碼驗證與流程圖後合併
```

## 首次啟用

1. 將工作流程、腳本與指引合併到此 repo 的預設分支（目前為 `master`）。
2. 在此 repo 的 **Actions** 頁面確認 workflow 已啟用。
3. 從 [Google AI Studio](https://aistudio.google.com/apikey) 取得 Gemini API key。
   在 **Settings → Secrets and variables → Actions → Secrets** 新增
   `GEMINI_API_KEY`，不要提交到 repo 或貼在 Issue、PR、對話中。
4. 可在同頁 **Variables** 設定 `GEMINI_MODEL`。預設為
   `gemini-3.8-flash`；請依自己的 API 專案權限與
   [模型目錄](https://ai.google.dev/gemini-api/docs/models) 選擇可用模型。
   Gemini API 的額度、地區限制與費用獨立於 GitHub Copilot 訂閱。
5. 在 **Settings → Actions → General → Workflow permissions** 允許
   **Allow GitHub Actions to create and approve pull requests**。
   本流程只建立 PR，不會呼叫核准 API；workflow 宣告最小必要的
   `contents: write` 與 `pull-requests: write`。
   若組織政策禁止，需先由管理員處理。
6. 到 **Actions → Generate OpenClaw Release Notes → Run workflow**，
   選擇預設分支，先將 `tag` 留空執行一次，確認成功建立 Draft PR。

不需要 PAT 或額外的 GitHub App 憑證。流程只建立 Draft PR，不會自動
核准或合併。

## 排程、補版與重複處理

- 每日 UTC 02:23（台灣時間 10:23）檢查；GitHub 排程可能延遲。
- 預設只取得官方 `/releases/latest`，首次執行先處理最新正式版，
  **不會一次補齊 5 月以來所有缺漏**，也不包含 prerelease。
- 要補歷史版本或兩次檢查之間被後續版本取代的版本，手動執行並指定
  完整 tag，例如 `v2026.5.3`。只能指定已公開的正式 Release。
- 檔名使用 tag 的版本日期，而非執行日期。同日修訂版（例如 `-1`）
  會附加到同一份日期文件，不覆蓋已收錄內容。
- 預設分支已有該版本的官方 URL，或該版本已有 PR（含已關閉 PR）
  時，不重新呼叫 Gemini、不重複建立。關閉 PR 表示人工拒絕該草稿；
  如需重做，先處理原 PR 與對應分支。
- 建 PR 失敗但分支已包含完整文件時，再次執行會沿用分支建立 PR。
  若分支僅建立但寫入失敗，流程會明確報錯，需人工檢查該分支後再重試。

## 人工審閱與驗證

Gemini 只收到公開的上游 release 內容、版本資訊及本 repo 的公開
`GUIDELINES.md`，不會讀取其他工作區內容，也沒有執行工具的權限。
上游文字視為資料而非指令。輸出經基本格式檢查，但不代表事實正確。
API 被拒絕、額度不足、輸出截斷或缺少必要章節時，流程失敗，不以
原文或空文件冒充成功；到 Actions 紀錄查看錯誤。

自動產物一律為 **Draft PR**，合併前依 `GUIDELINES.md` 核對：

- 翻譯、項目覆蓋、星級、引用與 Breaking Changes。
- 三星項目須人工查閱上游原始碼並補齊流程圖；AI 不會假裝已查過實作。
- 確認升級行動與摘要表，移除草稿警語並更新狀態後，才標記 ready 並合併。

本流程使用 `GITHUB_TOKEN` 建 PR，GitHub 通常不會因此觸發其他
`pull_request` 工作流程。若分支保護要求檢查，請依此 repo 的設定安排
必要檢查；不要為了合併而繞過分支保護。

公開 repo 的排程可能因長期無活動而被 GitHub 停用，請定期確認 Actions
仍啟用。此機制不依賴本機安裝 OpenClaw、OS crond 或 Telegram。

## 本地測試

```powershell
python -m unittest discover -s .github\scripts -p "test_*.py"
```

測試使用模擬 API，不會消耗 Gemini 額度或建立遠端分支／PR。
