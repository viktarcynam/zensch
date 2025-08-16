import re
from playwright.sync_api import sync_playwright, Page, expect
from datetime import date, timedelta

def run_verification(page: Page):
    """
    This script verifies the datalist functionality by manually entering
    a symbol and expiry date, which is more robust in a no-creds environment.
    """
    # 1. Go to the application homepage.
    page.goto("http://127.0.0.1:5001/")

    # 2. Get locators.
    symbol_input = page.get_by_placeholder("SYM")
    expiry_input = page.locator("#expiry-input")
    strike_input = page.locator("#strike-input")
    strike_datalist = page.locator("#strike-list")

    # 3. Wait for the app to initialize.
    expect(symbol_input).to_be_enabled(timeout=10000)

    # 4. Manually enter a symbol AND an expiry date.
    # This bypasses the dependency on /api/defaults, which fails in no-creds mode.
    # Entering an expiry date will directly trigger the 'fetchStrikes' function.
    symbol_input.fill("SPY")

    # Set a future date to ensure options exist.
    future_date = date.today() + timedelta(days=45)
    expiry_date_str = future_date.strftime('%Y-%m-%d')
    expiry_input.fill(expiry_date_str)

    # 5. Assert that the strike input now has a value (the default closest strike).
    # Increased timeout to allow for the API call to complete.
    expect(strike_input).to_have_value(re.compile(r"^\d+\.?\d*$"), timeout=15000)

    # 6. Assert that the datalist has been populated.
    expect(strike_datalist.locator("option")).to_have_count(20)

    # 7. Take a screenshot to visually verify the result.
    page.screenshot(path="jules-scratch/verification/datalist_verification.png")

# Boilerplate to run the script
if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            run_verification(page)
            print("Verification script ran successfully and created datalist_verification.png")
        except Exception as e:
            print(f"Verification script failed: {e}")
        finally:
            browser.close()
