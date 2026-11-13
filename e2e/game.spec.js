const { test, expect } = require("playwright/test");

function watchErrors(page) {
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  return errors;
}

async function noSideScroll(page) {
  const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(over).toBeLessThanOrEqual(0);
}

async function answerChoice(page, n = 1) {
  await page.getByLabel(`보기 ${n}`, { exact: true }).click();
  await page.getByRole("button", { name: /번으로 확정/ }).click();
  await expect(page.getByRole("button", { name: /다음 문제|결과 보기/ })).toBeVisible();
}

test("빠른 10문제(4지선다)를 끝까지 풀고 결과를 본다", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/");
  await noSideScroll(page);
  await page.getByRole("link", { name: /빠른 10문제/ }).click();
  await expect(page.getByText("문제 남음")).toBeVisible();
  await noSideScroll(page);
  await page.getByRole("button", { name: "시작" }).click();

  for (let i = 1; i <= 10; i++) {
    await expect(page.getByText(`${i} / 10`)).toBeVisible();
    await expect(page.getByRole("button", { name: "보기를 골라 주세요" })).toBeDisabled();
    await answerChoice(page, (i % 4) + 1);
    await expect(page.getByText(/정답!|아쉬워요|시간 초과/)).toBeVisible();
    await expect(page.getByText("실제", { exact: true })).toBeVisible();
    await expect(page.getByText("빈칸 수익률")).toBeVisible();
    if (i === 1) await noSideScroll(page);
    await page.getByRole("button", { name: /다음 문제|결과 보기/ }).click();
  }
  await expect(page.getByRole("heading", { name: "빠른 10문제 결과" })).toBeVisible();
  await expect(page.getByLabel(/10문제 중 \d+문제 정답/)).toBeVisible();
  await expect(page.getByText("문제별 결과")).toBeVisible();
  await noSideScroll(page);
  expect(errors).toEqual([]);
});

test("O/X 방식으로 10문제를 푼다", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/setup/quick");
  await page.getByRole("button", { name: /O \/ X/ }).click();
  await page.getByRole("button", { name: "시작" }).click();
  for (let i = 1; i <= 10; i++) {
    await expect(page.getByText(`${i} / 10`)).toBeVisible();
    await page.getByLabel(i % 2 ? "O, 실제다" : "X, 가짜다").click();
    await expect(page.getByText(/보여 드린 모양/)).toBeVisible();
    await page.getByRole("button", { name: /다음 문제|결과 보기/ }).click();
  }
  await expect(page.getByRole("heading", { name: "빠른 10문제 결과" })).toBeVisible();
  expect(errors).toEqual([]);
});

test("키보드만으로 풀 수 있다", async ({ page, isMobile }) => {
  test.skip(isMobile, "키보드는 데스크톱에서만 확인");
  await page.goto("/setup/endless");
  await page.getByRole("button", { name: "시작" }).click();
  await expect(page.getByLabel("보기 1", { exact: true })).toBeVisible();
  await page.keyboard.press("3");
  await expect(page.getByRole("button", { name: "3번으로 확정" })).toBeEnabled();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: "다음 문제" })).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(page.getByText("2번째")).toBeVisible();
});

test("새로고침해도 같은 문제가 이어진다", async ({ page }) => {
  await page.goto("/setup/quick");
  await page.getByRole("button", { name: "시작" }).click();
  await expect(page.getByText("1 / 10")).toBeVisible();
  await page.reload();
  await expect(page.getByText("1 / 10")).toBeVisible();
  await answerChoice(page, 1);
  await page.getByRole("button", { name: "다음 문제" }).click();
  await expect(page.getByText("2 / 10")).toBeVisible();
});

test("데일리 챌린지는 하루 한 번, 끝나면 순위표에 내가 보인다", async ({ page }) => {
  await page.goto("/daily");
  await page.getByRole("button", { name: "도전하기" }).click();
  for (let i = 1; i <= 5; i++) {
    await expect(page.getByText(`${i} / 5`)).toBeVisible();
    await answerChoice(page, 2);
    await page.getByRole("button", { name: /다음 문제|결과 보기/ }).click();
  }
  await expect(page.getByRole("heading", { name: "데일리 챌린지 결과" })).toBeVisible();
  await page.getByRole("link", { name: "순위 보기" }).click();
  await expect(page.getByText("오늘 문제는 다 풀었어요")).toBeVisible();
  await expect(page.getByRole("button", { name: "도전하기" })).toHaveCount(0);
  await expect(page.getByText("나", { exact: true })).toBeVisible();
  await page.getByLabel("순위표에 표시할 닉네임").fill("차트고수");
  await page.getByRole("button", { name: "저장" }).click();
  await expect(page.getByText("차트고수")).toBeVisible();
});

test("설정이 저장되고 내 기록이 쌓인다", async ({ page }) => {
  await page.goto("/stats");
  await expect(page.getByText("아직 푼 문제가 없어요")).toBeVisible();
  await page.getByRole("button", { name: "밝게" }).click();
  await page.getByRole("button", { name: "상승 초록 · 하락 빨강" }).click();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.locator("html")).toHaveAttribute("data-colors", "us");

  await page.goto("/setup/endless");
  await page.getByRole("button", { name: "시작" }).click();
  await answerChoice(page, 1);
  await page.goto("/stats");
  await expect(page.getByText("푼 문제")).toBeVisible();
  await expect(page.getByText("난이도별 정답률")).toBeVisible();
});
