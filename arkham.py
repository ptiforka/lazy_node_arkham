#!/usr/bin/env python3
import time
import re
import random
from playwright.sync_api import sync_playwright, Error as PlaywrightError

COOKIE_FILE = "cookies.txt"

# Proxy configuration (if needed)
PROXY_SERVER = "http://gate.nodemaven.com:8080"

ORDER_SELECTOR = '[data-testid="trade-tradeinfo-order-id-0"]'

def random_delay(min_delay=0.5, max_delay=2):
    time.sleep(random.uniform(min_delay, max_delay))

def parse_balance(balance_str):
    """Remove non-digit characters and convert to float."""
    clean_str = re.sub(r'[^\d\.]', '', balance_str)
    try:
        return float(clean_str)
    except Exception as e:
        print("Error parsing balance:", e)
        return 0.0

def get_balances(page):
    """
    Reads wallet balances from the page. Returns (sol_balance, usdt_balance).
    Adjusts based on the asset label.
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

    if 'SOL' in asset0_name.upper():
        sol_balance = asset0_balance
        usdt_balance = asset1_balance
    else:
        sol_balance = asset1_balance
        usdt_balance = asset0_balance - 1
    return sol_balance, usdt_balance

def move_mouse_to_element(page, selector):
    """Smoothly move the mouse to the center of the element."""
    element_handle = page.wait_for_selector(selector)
    box = element_handle.bounding_box()
    if not box:
        print(f"Could not get bounding box for {selector}")
        return
    target_x = box["x"] + box["width"] / 2
    target_y = box["y"] + box["height"] / 2
    steps = 20
    for i in range(1, steps + 1):
        page.mouse.move((target_x * i) / steps, (target_y * i) / steps)
        time.sleep(0.05)

def click_element(page, selector):
    """Move to an element, wait a bit, then click it."""
    page.wait_for_selector(selector, timeout=5000)
    move_mouse_to_element(page, selector)
    random_delay(0.5, 1.5)
    page.click(selector)
    random_delay(0.5, 1.5)

def cancel_order(page):
    """Attempt to cancel the active order.
    First try clicking normally; if that fails, force a click via JS.
    """
    cancel_button_selector = '.a480080.a99729a.ac07bd5.af77d85'
    try:
        cancel_locator = page.locator(cancel_button_selector).first
        cancel_locator.wait_for(state="visible", timeout=5000)
        cancel_locator.click()
        random_delay()
        print("Order cancelled normally.")
    except Exception as e:
        print("Error cancelling order normally:", e)
        try:
            print("Attempting force cancellation...")
            page.evaluate(f"document.querySelector('{cancel_button_selector}').click()")
            random_delay()
            print("Order cancelled using force.")
        except Exception as e2:
            print("Force cancellation failed:", e2)

def safe_query_selector(page, selector):
    """Query for an element while catching errors due to navigation/context destruction."""
    try:
        return page.query_selector(selector)
    except PlaywrightError as e:
        print(f"Error querying selector {selector}: {e}")
        return None

# --- Price Fetching Functions ---
def get_real_buy_price(page):
    """
    Fetch the real BUY price from the button with classes:
    "pl-3 text-green-900 undefined"
    """
    try:
        selector = "button.pl-3.text-green-900.undefined"
        element = page.wait_for_selector(selector, timeout=5000)
        price = (element.text_content() or "").strip()
        print(f"Fetched real BUY price: {price}")
        return price
    except Exception as e:
        print("Error fetching real BUY price:", e)
        return None

def compute_target_sell_price(page):
    """
    Compute the target SELL price by taking the real BUY price
    and adding a random increment between 0.01 and 0.04.
    """
    buy_price = get_real_buy_price(page)
    if not buy_price:
        print("Could not fetch real BUY price for computing SELL price.")
        return None
    try:
        buy_val = float(buy_price)
    except Exception as e:
        print("Error converting buy price to float:", e)
        return None
    increment = random.uniform(0.01, 0.04)
    target_sell_val = round(buy_val + increment, 2)
    target_sell_price = f"{target_sell_val:.2f}"
    print(f"Computed SELL price: {target_sell_price} (Buy price: {buy_price} + increment: {increment:.2f})")
    return target_sell_price

# --- Trade Functions ---
def trade_limit_buy_sol(page):
    """
    Place a limit BUY order using the real BUY price.
    BEFORE entering the order, click the BUY tab.
    After submission, perform up to 3 checks (5 sec each).
    If the fetched real price differs from the order price at any check,
    cancel the order and return False; otherwise, leave the order active.
    Finally, click the BUY tab.
    """
    print("=== Initiating Limit BUY Order ===")
    # Ensure BUY tab is active
    click_element(page, '[data-testid="trade-orderform-buy-tab"]')
    click_element(page, '[data-testid="trade-orderform-limit-tab"]')

    real_price = get_real_buy_price(page)
    if not real_price:
        print("Could not fetch real BUY price; aborting order.")
        return False
    last_order_price = real_price
    print(f"Using real BUY price: {last_order_price}")

    limit_price_input_selector = '[data-testid="trade-orderform-limit-price-input"]'
    page.wait_for_selector(limit_price_input_selector)
    move_mouse_to_element(page, limit_price_input_selector)
    random_delay()
    page.fill(limit_price_input_selector, last_order_price)
    random_delay()

    sol_balance, usdt_balance = get_balances(page)
    print(f"Current balances - SOL: {sol_balance}, USDT: {usdt_balance}")

    random_percent = random.uniform(0.60, 0.95)
    deduction = random.uniform(1, 2)
    available_for_trade = usdt_balance - deduction
    if available_for_trade <= 0:
        print("Not enough USDT after deduction.")
        return False
    trade_amount = round(available_for_trade * random_percent, 3)
    print(f"Using {trade_amount} USDT for BUY order (percent: {random_percent:.2f}, deduction: {deduction:.2f}).")

    notional_input_selector = '[data-testid="trade-orderform-notional-input"]'
    page.wait_for_selector(notional_input_selector)
    move_mouse_to_element(page, notional_input_selector)
    random_delay()
    page.fill(notional_input_selector, str(trade_amount))
    random_delay()

    # Re-read real price before submission
    new_price = get_real_buy_price(page)
    if new_price and new_price != last_order_price:
        print(f"Real BUY price changed from {last_order_price} to {new_price} before submission. Updating.")
        page.fill(limit_price_input_selector, new_price)
        last_order_price = new_price
        random_delay()

    click_element(page, '[data-testid="trade-orderform-submit-button"]')

    # Perform up to 3 checks (5 sec each)
    check_count = 0
    while check_count < 3:
        time.sleep(5)
        order_present = safe_query_selector(page, ORDER_SELECTOR)
        if not order_present:
            print("BUY order filled; no active order found.")
            click_element(page, '[data-testid="trade-orderform-buy-tab"]')
            return True
        current_real_price = get_real_buy_price(page)
        if current_real_price != last_order_price:
            print(f"Check {check_count+1}: Price changed from {last_order_price} to {current_real_price}. Cancelling BUY order.")
            cancel_order(page)
            click_element(page, '[data-testid="trade-orderform-buy-tab"]')
            return False
        else:
            print(f"Check {check_count+1}: Real BUY price unchanged at {current_real_price}.")
        check_count += 1

    print("After 3 checks, active BUY order still exists. Cancelling and recreating order.")
    cancel_order(page)
    click_element(page, '[data-testid="trade-orderform-buy-tab"]')
    return False

def trade_limit_sell_sol(page):
    """
    Place a limit SELL order by computing the target as (buy price + random increment).
    BEFORE entering the order, click the SELL tab.
    After submission, perform up to 3 checks (5 sec each).
    In each check, recompute the target SELL price using the current buy price.
    If it differs from the order price placed (last_order_price), cancel the order and return False;
    otherwise, leave the order active.
    Finally, click the SELL tab.
    """
    print("=== Initiating Limit SELL Order ===")
    click_element(page, '[data-testid="trade-orderform-sell-tab"]')
    click_element(page, '[data-testid="trade-orderform-limit-tab"]')
    click_element(page, '[data-testid="trade-orderform-sell-tab"]')  # Ensure sell form is active

    target_sell_price = compute_target_sell_price(page)
    if not target_sell_price:
        print("Could not compute target SELL price; aborting order.")
        return False
    last_order_price = target_sell_price
    print(f"Using target SELL price: {last_order_price}")

    limit_price_input_selector = '[data-testid="trade-orderform-limit-price-input"]'
    page.wait_for_selector(limit_price_input_selector)
    move_mouse_to_element(page, limit_price_input_selector)
    random_delay()
    page.fill(limit_price_input_selector, last_order_price)
    random_delay()

    sol_balance, usdt_balance = get_balances(page)
    print(f"Current balances - SOL: {sol_balance}, USDT: {usdt_balance}")

    random_percent = random.uniform(0.60, 0.95)
    trade_amount = round(sol_balance * random_percent, 3)
    print(f"Selling {trade_amount} SOL for SELL order (percent: {random_percent:.2f}).")

    size_input_selector = '[data-testid="trade-orderform-size-input"]'
    page.wait_for_selector(size_input_selector)
    move_mouse_to_element(page, size_input_selector)
    random_delay()
    page.fill(size_input_selector, str(trade_amount))
    random_delay()

    # Recompute target SELL price before submission
    new_target = compute_target_sell_price(page)
    if new_target and new_target != last_order_price:
        print(f"Computed target SELL price changed from {last_order_price} to {new_target} before submission. Updating.")
        page.fill(limit_price_input_selector, new_target)
        last_order_price = new_target
        random_delay()

    click_element(page, '[data-testid="trade-orderform-submit-button"]')

    # Perform up to 3 checks (5 sec each)
    check_count = 0
    while check_count < 3:
        time.sleep(5)
        order_present = safe_query_selector(page, ORDER_SELECTOR)
        if not order_present:
            print("SELL order filled; no active order found.")
            click_element(page, '[data-testid="trade-orderform-sell-tab"]')
            return True
        new_target = compute_target_sell_price(page)
        if new_target != last_order_price:
            print(f"Check {check_count+1}: Computed target SELL price changed from {last_order_price} to {new_target}. Cancelling SELL order.")
            cancel_order(page)
            click_element(page, '[data-testid="trade-orderform-sell-tab"]')
            return False
        else:
            print(f"Check {check_count+1}: Computed target SELL price unchanged at {new_target}.")
        check_count += 1

    print("After 3 checks, active SELL order still exists. Cancelling and recreating order.")
    cancel_order(page)
    click_element(page, '[data-testid="trade-orderform-sell-tab"]')
    return False

def add_initial_cookies(context):
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
    if cookies:
        context.add_cookies(cookies)

def save_cookies_to_file(context):
    cookies = context.cookies()
    with open(COOKIE_FILE, "w") as f:
        for cookie in cookies:
            f.write(f"{cookie['name']}={cookie['value']}\n")
    print("Cookies saved to", COOKIE_FILE)

def main():
    with sync_playwright() as p:
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36"
        )
        print("Using user agent:", user_agent)
        browser = p.chromium.launch(
            headless=False,
            proxy={"server": PROXY_SERVER,
                   "username": PROXY_USERNAME,
                   "password": PROXY_PASSWORD}
        )
        context = browser.new_context(user_agent=user_agent)
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
            Object.defineProperty(navigator, 'appVersion', { get: () => '5.0 (Windows NT 10.0; Win64; x64)' });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            sessionStorage.setItem('metamaskConfig', JSON.stringify({
                hideProvidersArray: false,
                showMetamaskExplainer: false,
                dontOverrideWindowEthereum: false
            }));
            const dbName = "WALLET_CONNECT_V2_INDEXED_DB";
            const storeName = "keyvaluepairs";
            const key = "wc@2:core:0.3:keychain";
            const value = JSON.stringify({});
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
        add_initial_cookies(context)

        page = context.new_page()
        page.goto("https://arkm.com/trade/SOL_USDT")
        page.wait_for_load_state("networkidle")
        time.sleep(3)
        save_cookies_to_file(context)

        print("Starting trade loop. Press Ctrl+C to stop.")
        transaction_type = 'buy'
        active_order_count = 0
        try:
            while True:
                try:
                    active_order = safe_query_selector(page, ORDER_SELECTOR)
                except Exception as e:
                    print("Error checking active order:", e)
                    active_order = None

                if active_order:
                    active_order_count += 1
                    print(f"Active order exists. Count: {active_order_count}. Waiting for resolution before starting a new trade.")
                    if active_order_count >= 3:
                        print("Active order detected 3 times consecutively. Cancelling active order.")
                        cancel_order(page)
                        active_order_count = 0
                    time.sleep(10)
                    continue
                else:
                    active_order_count = 0

                if transaction_type == 'buy':
                    print("\nAttempting LIMIT BUY order...")
                    success = trade_limit_buy_sol(page)
                    if success:
                        active_order = safe_query_selector(page, ORDER_SELECTOR)
                        if not active_order:
                            transaction_type = 'sell'
                    else:
                        print("BUY order not executed. Retrying BUY order...")
                else:
                    print("\nAttempting LIMIT SELL order...")
                    success = trade_limit_sell_sol(page)
                    if success:
                        active_order = safe_query_selector(page, ORDER_SELECTOR)
                        if not active_order:
                            transaction_type = 'buy'
                    else:
                        print("SELL order not executed. Retrying SELL order...")
                random_delay(2, 5)
        except KeyboardInterrupt:
            print("Exiting trade loop...")
            browser.close()

if __name__ == "__main__":
    main()

