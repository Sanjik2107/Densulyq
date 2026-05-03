import { expect, test } from '@playwright/test'

const AUTH_KEY = 'densaulyq-auth-v2'
const E2E_REASON = 'Playwright patient booking'

function controlIn(container, label, selector = 'input, textarea, select') {
  return container
    .locator('.fg')
    .filter({ hasText: new RegExp(`^${label}`) })
    .locator(selector)
    .first()
}

async function login(page, username, password) {
  await page.goto('/')
  const form = page.locator('.auth-box')
  await controlIn(form, 'Username', 'input').fill(username)
  await controlIn(form, 'Password', 'input').fill(password)
  await page.getByRole('button', { name: 'Login' }).click()
  await page.locator('.auth-box input[placeholder="000000"], .topbar h1').first().waitFor({ state: 'visible' })
  const mfaInput = form.locator('input[placeholder="000000"]')
  if (await mfaInput.isVisible().catch(() => false)) {
    const hint = await form.textContent()
    const code = hint.match(/\d{6}/)?.[0]
    expect(code).toBeTruthy()
    await mfaInput.fill(code)
    await page.getByRole('button', { name: 'Verify' }).click()
  }
  await expect(page.getByRole('heading', { name: /Dashboard|Admin panel|Lab workspace/ })).toBeVisible()
}

async function authToken(page) {
  return page.evaluate((key) => JSON.parse(localStorage.getItem(key) || '{}').token, AUTH_KEY)
}

test('patient can book a visit from dashboard and cancel it through API cleanup', async ({ page, request }) => {
  await login(page, 'patient-demo', 'patient123')

  await page.getByRole('button', { name: 'Book a visit' }).click()
  const modal = page.locator('.modal').filter({ has: page.getByRole('heading', { name: 'Book appointment' }) })
  await expect(modal).toBeVisible()

  await controlIn(modal, 'Doctor', 'select').selectOption({ index: 1 })
  await controlIn(modal, 'Date', 'input').fill('2099-05-10')
  await expect(controlIn(modal, 'Session time', 'select')).toBeEnabled()
  await controlIn(modal, 'Session time', 'select').selectOption({ index: 1 })
  await controlIn(modal, 'Reason', 'textarea').fill(E2E_REASON)

  const createResponse = page.waitForResponse((response) =>
    response.url().endsWith('/appointments') && response.request().method() === 'POST'
  )
  await modal.getByRole('button', { name: 'Book', exact: true }).click()
  const created = await (await createResponse).json()

  await expect(page.getByText('Appointment request submitted.')).toBeVisible()

  const token = await authToken(page)
  await request.patch(`/appointments/${created.id}/cancel`, {
    headers: { Authorization: `Bearer ${token}` },
  })
})

test('doctor can select patient and open book visit modal', async ({ page }) => {
  await login(page, 'doctor-demo', 'doctor123')

  await expect(page.getByText('Patients in focus')).toBeVisible()
  await page.getByRole('cell', { name: 'Алибек Джаксыбеков' }).click()
  await expect(page.getByText('Visits scheduled for this patient')).toBeVisible()
  await expect(page.getByText('Active directions linked to this patient')).toBeVisible()

  await page.getByRole('button', { name: 'Book visit' }).click()
  const modal = page.locator('.modal').filter({ has: page.getByRole('heading', { name: 'Book visit' }) })
  await expect(modal).toBeVisible()
  await expect(controlIn(modal, 'Patient', 'input')).toHaveValue('Алибек Джаксыбеков')
})

test('admin can open user management and audit log', async ({ page }) => {
  await login(page, 'admin-demo', 'admin123')

  await expect(page.getByRole('heading', { name: 'Admin panel' })).toBeVisible()
  await expect(page.getByText('Create new user')).toBeVisible()
  await expect(page.getByText('Audit log')).toBeVisible()
})

test('lab can open analysis update modal', async ({ page }) => {
  await login(page, 'lab-demo', 'lab123')

  await expect(page.getByRole('heading', { name: 'Lab workspace' })).toBeVisible()
  await page.getByRole('button', { name: 'Update' }).first().click()
  await expect(page.getByRole('heading', { name: 'Update analysis' })).toBeVisible()
})
