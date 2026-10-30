# OpenClaw 繁體中文發佈說明

此獨立 repo 專門整理 [OpenClaw](https://github.com/openclaw/openclaw) 的繁體中文發佈說明。GitHub Actions 會定期檢查官方最新正式版，使用 Google Gemini API 產生待審閱草稿，並建立 **Draft Pull Request**；不會自動核准或合併。

## 內容與流程

- 發佈說明存放於 `release-notes/YYYY-MM-DD.md`，日期取自版本 tag。
- `release-notes/GUIDELINES.md` 定義繁中格式、內容與人工審閱要求。
- 自動草稿只根據公開的官方 Release 內容產生，不會假裝已查閱上游原始碼。合併前須人工核對內容，並為三星項目查閱原始碼、補上流程圖。
- `release-notes/CHECK_UPDATE.md` 說明啟用、手動補版、重複處理與審閱流程。

## 啟用

1. 將自動化檔案合併至此 repo 的預設分支。
2. 在 repo 的 **Settings → Secrets and variables → Actions → Secrets** 新增 `GEMINI_API_KEY`。金鑰只應存為 GitHub Actions Secret，不要提交至 repo 或貼在 Issue、PR、對話中。
3. 確認 **Settings → Actions → General → Workflow permissions** 允許 Actions 建立 Pull Request。工作流程只要求 `contents: write` 與 `pull-requests: write`，且只建立 Draft PR。
4. 前往 **Actions → Generate OpenClaw Release Notes → Run workflow**，先不填 `tag`，手動測試最新正式版。也可在 `GEMINI_MODEL` repo variable 指定可用的 Gemini 模型；未設定時使用 `gemini-3.8-flash`。

排程、API 額度與費用、手動指定 tag 補歷史版本及分支保護注意事項，請參閱[自動更新說明](release-notes/CHECK_UPDATE.md)。

## 本地測試

```powershell
python -m unittest discover -s .github\scripts -p "test_*.py"
```

測試使用模擬 API，不會呼叫 Gemini，也不會建立遠端分支或 Pull Request。
