import re
from playwright.sync_api import sync_playwright, Page, expect
from datetime import date, timedelta

def run_verification(page: Page):
    """
    This script verifies that the strike input has been converted to a dropdown
    and that it populates with strikes after entering a symbol and expiry.
    """
    # 1. Go to the application homepage.
    page.goto("http://127.0.0.1:5001/")

    # 2. Get locators for the elements we will interact with.
    symbol_input = page.get_by_placeholder("SYM")
    expiry_input = page.locator("#expiry-input")
    strike_dropdown = page.locator("#strike-input")

    # 3. Wait for the app to initialize by checking the status display.
    # This ensures the backend connection is established before we proceed.
    expect(page.locator("#status-display")).to_have_text("Idle")

    # 4. Enter a symbol and press Enter to trigger the 'change' event.
    # This should cause the app to fetch and set a default expiry date.
    symbol_input.fill("SPY")
    symbol_input.press("Enter")

    # 5. Wait for the expiry date input to be populated.
    expect(expiry_input).not_to_have_value("")

    # 6. Assert that the strike dropdown is populated with valid strikes.
    # The fetchStrikes function is now triggered. We wait for the "Loading..."
    # message to disappear and for the first option to be a valid number.
    expect(strike_dropdown.locator("option").first).to_have_attribute("value", re.compile(r"^\d+\.?\d*$"))

    # 7. Take a screenshot to visually verify the result.
    page.screenshot(path="jules-scratch/verification/verification.png")

# Boilerplate to run the script
if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            run_verification(page)
            print("Verification script ran successfully and created verification.png")
        except Exception as e:
            print(f"Verification script failed: {e}")
        finally:
            browser.close()
