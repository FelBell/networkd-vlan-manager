import os
import time
import subprocess
from playwright.sync_api import sync_playwright

def run_verification():
    # Start the app
    # Use a port that is free
    port = "5001"

    # We need to run python -m vlan_manager.app.app because wsgi.py hardcodes port 5000 in app.run().
    # Actually, wsgi.py calls app.run(host='0.0.0.0', port=5000).
    # I should modify wsgi.py to accept port from env or just stick to 5000.
    # Sticking to 5000 is fine if nothing is running.

    env = os.environ.copy()
    env['DATA_FILE'] = '/tmp/vlans_verify.json'

    # Clean up previous run data
    if os.path.exists('/tmp/vlans_verify.json'):
        os.remove('/tmp/vlans_verify.json')

    print("Starting server...")
    server_process = subprocess.Popen(['python3', 'wsgi.py'], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    try:
        # Check if server started
        for _ in range(10):
            time.sleep(1)
            # Check if port is open? Or just try to connect.
            if server_process.poll() is not None:
                out, err = server_process.communicate()
                print(f"Server exited early: {err.decode()}")
                return

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            print("Navigating to login...")
            try:
                page.goto("http://localhost:5000/login")
            except Exception as e:
                print(f"Failed to load page: {e}")
                server_process.terminate()
                out, err = server_process.communicate()
                print("Server Output:", out.decode())
                print("Server Error:", err.decode())
                return

            print("Logging in...")
            page.fill("input[name='username']", "admin")
            page.fill("input[name='password']", "password")
            page.click("button[type='submit']")

            # Check dashboard
            print("Verifying dashboard...")
            try:
                page.wait_for_selector("h1:text('VLAN Manager')", timeout=5000)
            except Exception as e:
                print("Dashboard header not found.")
                page.screenshot(path="verification/error_login.png")
                raise e

            # Add VLAN
            print("Adding VLAN...")
            page.fill("input[name='id']", "50")
            page.fill("input[name='cidr']", "10.10.50.1/24")
            page.check("input[name='dhcp']")
            page.click("button:text('Add VLAN')")

            # Verify it appears
            print("Verifying VLAN in list...")
            try:
                page.wait_for_selector("td:text('10.10.50.1/24')", timeout=5000)
            except Exception as e:
                print("VLAN not found in table.")
                page.screenshot(path="verification/error_add.png")
                raise e

            # Screenshot
            if not os.path.exists("verification"):
                os.makedirs("verification")
            page.screenshot(path="verification/dashboard.png")
            print("Verification successful, screenshot saved to verification/dashboard.png.")

    finally:
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except:
            server_process.kill()

if __name__ == "__main__":
    run_verification()
