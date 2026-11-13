// 브라우저 자동 테스트. 합성 데이터로 만든 임시 DB로 서버를 띄운 뒤 실제 화면을 조작한다.
const { defineConfig, devices } = require("playwright/test");
const os = require("os");
const path = require("path");

const PORT = 8799;
const db = path.join(os.tmpdir(), `chartgap-e2e-${process.pid}.db`);

module.exports = defineConfig({
  testDir: ".",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: `http://127.0.0.1:${PORT}`, locale: "ko-KR", colorScheme: "dark" },
  projects: [
    { name: "mobile", use: { ...devices["iPhone 13"], browserName: "chromium" } },
    { name: "desktop", use: { viewport: { width: 1280, height: 900 } } },
  ],
  webServer: {
    command: `.venv/bin/python ../e2e/make_synth_db.py sqlite:///${db} && .venv/bin/uvicorn chartgame.api.main:app --port ${PORT}`,
    cwd: path.join(__dirname, "..", "backend"),
    url: `http://127.0.0.1:${PORT}/api/health`,
    env: { CHARTGAME_DB: `sqlite:///${db}`, CHARTGAME_RATE_LIMIT: "0" },
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
