#!/usr/bin/env python3
import time
import re
import uuid
import random
from playwright.sync_api import sync_playwright

COOKIE_FILE = "cookies.txt"

# Proxy credentials extracted from your provided string:
# http://USERNAME:PASSWORD@gate.nodemaven.com:8080
PROXY_SERVER = "http://gate.nodemaven.com:8080"
PROXY_USERNAME = ""
PROXY_PASSWORD = ""

def random_delay():
    """Sleep for a random interval between 0.5 and 3 seconds."""
    delay = random.uniform(0.5, 3)
    time.sleep(delay)

def parse_balance(balance_str):
    """Remove non-digit/decimal characters and convert to float."""
    clean_str = re.sub(r'[^\d\.]', '', balance_str)
    try:
        return float(clean_str)
    except:
        return 0.0

def get_balances(page):
    """
    Dynamically detect which balance is SOL and which is USDT
    by reading their labels. Returns (sol_balance, usdt_balance).
    """
    asset0_name_sel = '[data-testid="trade-wallet-asset-name-0"]'
    asset1_name_sel = '[data-testid="trade-wallet-asset-name-1"]'
    asset0_free_sel = '[data-testid="trade-wallet-asset-free-0"]'
    asset1_free_sel = '[data-testid="trade-wallet-asset-free-1"]'

    page.wait_for_selector(asset0_name_sel)
    page.wait_for_selector(asset1_name_sel)

    asset0_name = (page.text_content(asset0_name_sel) or '').strip()
    asset1_name = (page.text_content(asset1_name_sel) or '').strip()

    asset0_balance_str = (page.text_content(asset0_free_sel) or '').strip()
    asset1_balance_str = (page.text_content(asset1_free_sel) or '').strip()

    asset0_balance = parse_balance(asset0_balance_str)
    asset1_balance = parse_balance(asset1_balance_str)

    # Decide which is SOL vs. USDT based on the name text
    if 'SOL' in asset0_name.upper():
        sol_balance = asset0_balance
        usdt_balance = asset1_balance
    else:
        sol_balance = asset1_balance
        usdt_balance = asset0_balance - 1

    return sol_balance, usdt_balance

def move_mouse_to_element(page, selector):
    """Simulate smooth mouse movement to the center of the element."""
    element_handle = page.wait_for_selector(selector)
    box = element_handle.bounding_box()
    if not box:
        print(f"Could not get bounding box for {selector}")
        return
    target_x = box["x"] + box["width"] / 2
    target_y = box["y"] + box["height"] / 2

    # For simplicity, assume the mouse starts at (0,0).
    # We'll do ~20 small steps to simulate movement.
    steps = 20
    for i in range(1, steps + 1):
        new_x = (target_x * i) / steps
        new_y = (target_y * i) / steps
        page.mouse.move(new_x, new_y)
        time.sleep(0.05)

def click_element(page, selector):
    """Move mouse to the element, wait a random delay, then click it."""
    page.wait_for_selector(selector, timeout=5000)
    move_mouse_to_element(page, selector)
    random_delay()
    page.click(selector)
    random_delay()

def trade_sell_sol(page):
    """
    Sell a random 30–95% of the user's SOL balance (rounded to 3 decimals).
    Fills `data-testid="trade-orderform-size-input"`.
    Then clicks the Sell tab and Sell button.
    """
    sol_balance, usdt_balance = get_balances(page)
    print(f"Detected balances: SOL={sol_balance}, USDT={usdt_balance}")

    percent = random.uniform(0.30, 0.95)
    trade_amount = round(sol_balance * percent, 3)
    print(f"Selling {trade_amount} SOL ({percent*100:.1f}% of SOL)")

    # Fill the size input
    size_input_selector = '[data-testid="trade-orderform-size-input"]'
    page.wait_for_selector(size_input_selector)
    move_mouse_to_element(page, size_input_selector)
    random_delay()
    page.fill(size_input_selector, str(trade_amount))
    random_delay()

    # Click the Sell tab
    sell_tab_selector = '[data-testid="trade-orderform-sell-tab"]'
    click_element(page, sell_tab_selector)

    # Click the Sell submit button
    sell_button_selector = '[data-testid="trade-orderform-submit-button"]'
    click_element(page, sell_button_selector)

def trade_buy_sol(page):
    """
    Buy SOL using the entire USDT balance (rounded to 3 decimals).
    Fills `data-testid="trade-orderform-notional-input"`.
    Then clicks the Buy tab and Buy button.
    """
    sol_balance, usdt_balance = get_balances(page)
    print(f"Detected balances: SOL={sol_balance}, USDT={usdt_balance}")

    trade_amount = round(usdt_balance, 3)
    print(f"Buying SOL with {trade_amount} USDT")

    # Fill the notional input (for USDT)
    notional_input_selector = '[data-testid="trade-orderform-notional-input"]'
    page.wait_for_selector(notional_input_selector)
    move_mouse_to_element(page, notional_input_selector)
    random_delay()
    buy_tab_selector = '[data-testid="trade-orderform-buy-tab"]'
    click_element(page, buy_tab_selector)
    random_delay()
    page.fill(notional_input_selector, str(trade_amount))
    random_delay()

    # Click the Buy tab

    # Click the Buy submit button
    buy_button_selector = '[data-testid="trade-orderform-submit-button"]'
    click_element(page, buy_button_selector)

def add_initial_cookies(context):
    """Parse the provided cookie string and add initial cookies to the browser context."""
    cookie_string = (
  
    )
    cookies = []
    for part in cookie_string.split(";"):
        part = part.strip()
        if "=" in part:
            name, value = part.split("=", 1)
            cookies.append({
                "name": name,
                "value": value,
                "domain": "arkm.com",
                "path": "/"
            })
    context.add_cookies(cookies)

def save_cookies_to_file(context):
    """Save cookies from the context to a file."""
    cookies = context.cookies()
    with open(COOKIE_FILE, "w") as f:
        for cookie in cookies:
            f.write(f"{cookie['name']}={cookie['value']}\n")
    print("Cookies saved to", COOKIE_FILE)

def main():
    with sync_playwright() as p:
        # Launch Chromium with a proxy and a "normal" user agent
        # (You can randomize or choose a specific one.)
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36"
        )
        print("Using user agent:", user_agent)

        browser = p.chromium.launch(
            headless=False,
            proxy={
                "server": PROXY_SERVER,
                "username": PROXY_USERNAME,
                "password": PROXY_PASSWORD,
            }
        )

        # Create a new browser context with the user agent
        context = browser.new_context(user_agent=user_agent)

        # Inject anti-detection + sessionStorage + IndexedDB overrides
        context.add_init_script("""
            // Basic anti-detection
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
            Object.defineProperty(navigator, 'appVersion', {
                get: () => '5.0 (Windows NT 10.0; Win64; x64)'
            });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });

            // Set sessionStorage item
            sessionStorage.setItem('metamaskConfig', JSON.stringify({
                hideProvidersArray: false,
                showMetamaskExplainer: false,
                dontOverrideWindowEthereum: false
            }));

            // Set IndexedDB value
            const dbName = "WALLET_CONNECT_V2_INDEXED_DB";
            const storeName = "keyvaluepairs";
            const key = "wc@2:core:0.3:keychain";
            const value = JSON.stringify({
               
            });
            const openRequest = indexedDB.open(dbName);
            openRequest.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains(storeName)) {
                    db.createObjectStore(storeName);
                }
            };
            openRequest.onerror = (e) => { console.error(e.target.error); };
            openRequest.onsuccess = (e) => {
                const db = e.target.result;
                const tx = db.transaction(storeName, "readwrite");
                const store = tx.objectStore(storeName);
                store.put(value, key);
                tx.oncomplete = () => { db.close(); };
            };
        """)

        # Add initial cookies
        add_initial_cookies(context)

        # Create page and navigate
        page = context.new_page()
        page.goto("https://arkm.com/trade/SOL_USDT")
        page.wait_for_load_state("networkidle")
        time.sleep(3)
        save_cookies_to_file(context)

        print("Starting trade loop. Press Ctrl+C to stop.")
        try:
            while True:
                # SELL SOL
                click_element(page, '[data-testid="trade-orderform-market-tab"]')
                page.wait_for_load_state("networkidle")
                random_delay()
                trade_sell_sol(page)

                # BUY SOL
                random_delay()
                trade_buy_sol(page)

                # Wait a bit before repeating
                random_delay()
        except KeyboardInterrupt:
            print("Exiting trade loop...")
            browser.close()

if __name__ == "__main__":
    main()
