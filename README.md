# OpenClaw 繁體中文發佈說明

此獨立 repo 專門整理 [OpenClaw](https://github.com/openclaw/openclaw) 的繁體中文發佈說明。GitHub Actions 會定期檢查官方最新正式版，透過 OpenRouter `openrouter/free` 產生待審閱草稿，並建立 **Draft Pull Request**；不會自動核准或合併。免費 router 受服務狀態與配額限制，可能回傳 429/502，不能保證可用或永遠免費；產生內容必須人工審閱。

## 內容與流程

- 發佈說明存放於 `release-notes/YYYY-MM-DD.md`，日期取自版本 tag。
- `release-notes/GUIDELINES.md` 定義繁中格式、內容與人工審閱要求。
- 自動草稿會同時讀取公開的 GitHub Release 內容，以及 tag 對應的官方 `CHANGELOG/<版本>.md`（例如 `v2026.5.3` 對應 `CHANGELOG/2026.5.3.md`），並在草稿與 PR 說明標示來源。上游文字視為不可信資料；不會依 release 文字中的 URL 擷取來源，也不會假裝已查閱上游原始碼。
- 若版本專屬 changelog 回傳 404，草稿會明確標示只根據 Release 內容、可能不完整；其他擷取錯誤會停止流程。輸出檢查會從官方 changelog 的 Highlights、Changes、Fixes 等清單項目擷取 `(#PR)` 編號或官方 PR URL，要求有來源候選編號的分類至少產出一則含詳情及可驗證官方 PR 連結的項目；Highlights/Changes 保守視為未分類。沒有候選編號的分類可保持空白，且不保證涵蓋完整或事實正確。
- 合併前仍須人工核對內容，並為三星項目查閱原始碼、補上流程圖。
- `release-notes/CHECK_UPDATE.md` 說明啟用、手動補版、重複處理與審閱流程。

## 啟用

1. 將自動化檔案合併至此 repo 的預設分支。
2. 在 repo 的 **Settings → Secrets and variables → Actions → Secrets** 新增 `OPENROUTER_API_KEY`。金鑰只應存為 GitHub Actions Secret，不要提交至 repo 或貼在 Issue、PR、對話中。產生器固定使用 OpenRouter API 的 `openrouter/free` 模型，不需設定模型變數。
3. 確認 **Settings → Actions → General → Workflow permissions** 允許 Actions 建立 Pull Request。工作流程只要求 `contents: write` 與 `pull-requests: write`，且只建立 Draft PR。
4. 前往 **Actions → Generate OpenClaw Release Notes → Run workflow**，先不填 `tag`，手動測試最新正式版。

排程、API 額度與費用、手動指定 tag 補歷史版本及分支保護注意事項，請參閱[自動更新說明](release-notes/CHECK_UPDATE.md)。

## 本地測試

```powershell
python -m unittest discover -s .github\scripts -p "test_*.py"
```

測試使用模擬 API，不會呼叫 OpenRouter，也不會建立遠端分支或 Pull Request。
