"""
wifi_setup.py — AP-mode WiFi credential change UI.

How it works:
  1. Device creates a temporary WiFi access point ("M5Stack-Setup", open/no password)
  2. display.show_wifi_setup() shows instructions on screen
  3. User (or evaluator) connects their phone/laptop to that AP
  4. Opens 192.168.4.1 in a browser — sees a simple HTML form
  5. Enters new SSID + password, submits
  6. Device saves credentials via config.save_wifi_creds() then reboots
  7. boot.py reconnects with the new credentials on next power-on

This is tested during evaluation ("change to iot-unil" scenario).
Triggered from main.py when Button C is held for 3 seconds.

Auto-cancels after TIMEOUT_S seconds if no form submission is received.
"""
import network
import usocket
import machine
import utime
import config
import display

AP_SSID    = "M5Stack-Setup"
AP_PASS    = ""        # open AP — no password required
TIMEOUT_S  = 120       # give up after 2 minutes


# ── HTML responses ────────────────────────────────────────────────────────────

_PAGE = """\
HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n\
<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>M5Stack WiFi Setup</title>
<style>
  body{font-family:sans-serif;max-width:380px;margin:40px auto;padding:16px}
  h2{color:#0078D7}
  label{display:block;margin-top:12px;font-weight:bold}
  input{width:100%;padding:10px;margin-top:4px;font-size:16px;
        box-sizing:border-box;border:1px solid #ccc;border-radius:4px}
  button{margin-top:20px;width:100%;padding:14px;background:#0078D7;
         color:#fff;border:none;border-radius:4px;font-size:18px;cursor:pointer}
</style>
</head>
<body>
<h2>M5Stack WiFi Setup</h2>
<form method="POST" action="/save">
  <label>Network (SSID)
    <input name="ssid" type="text" autocapitalize="none" autocorrect="off">
  </label>
  <label>Password
    <input name="password" type="password">
  </label>
  <button type="submit">Save &amp; Reboot</button>
</form>
</body></html>"""

_PAGE_OK = """\
HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n\
<!DOCTYPE html>
<html><body style="font-family:sans-serif;text-align:center;padding:60px">
<h2 style="color:green">&#10003; Saved!</h2>
<p>M5Stack is rebooting.<br>Reconnect your device to <strong>your</strong> WiFi.</p>
</body></html>"""

_PAGE_ERR = """\
HTTP/1.0 400 Bad Request\r\nContent-Type: text/html\r\n\r\n\
<!DOCTYPE html>
<html><body style="font-family:sans-serif;padding:40px">
<h2 style="color:red">Missing SSID</h2>
<p>Please enter a network name.</p>
<a href="/">&#8592; Try again</a>
</body></html>"""


# ── URL-decode helpers ────────────────────────────────────────────────────────

def _urldecode(s):
    """Minimal percent-decoding for form fields (handles %XX and + → space)."""
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "+":
            out.append(" ")
        elif c == "%" and i + 2 < len(s):
            try:
                out.append(chr(int(s[i + 1:i + 3], 16)))
                i += 2
            except ValueError:
                out.append(c)
        else:
            out.append(c)
        i += 1
    return "".join(out)


def _parse_form(body):
    """Parse application/x-www-form-urlencoded → dict."""
    params = {}
    for pair in body.split("&"):
        if "=" in pair:
            k, _, v = pair.partition("=")
            params[_urldecode(k)] = _urldecode(v)
    return params


# ── AP web server ─────────────────────────────────────────────────────────────

def enter():
    """
    Start AP mode and serve the credential-change form.
    Blocks until a valid form is submitted or TIMEOUT_S elapses.
    Returns True if credentials were saved (device will reset), False on timeout.
    """
    # ── Start access point ────────────────────────────────────────────────────
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=AP_SSID, password=AP_PASS, authmode=0)  # 0 = open

    display.show_wifi_setup()

    # ── Minimal HTTP server on port 80 ────────────────────────────────────────
    srv = usocket.socket(usocket.AF_INET, usocket.SOCK_STREAM)
    srv.setsockopt(usocket.SOL_SOCKET, usocket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", 80))
    srv.listen(1)
    srv.settimeout(2)         # non-blocking accept with 2 s poll interval

    deadline = utime.time() + TIMEOUT_S
    saved = False

    try:
        while utime.time() < deadline:
            remaining = deadline - utime.time()
            display.show_status(
                "AP: {} — {}s left".format(AP_SSID, remaining), display.ACCENT
            )

            try:
                conn, _ = srv.accept()
            except OSError:
                continue  # timeout on accept — poll again

            try:
                raw = conn.recv(2048).decode("utf-8", "ignore")

                if raw.startswith("POST /save"):
                    # Body follows the blank line \r\n\r\n
                    if "\r\n\r\n" in raw:
                        body = raw.split("\r\n\r\n", 1)[1]
                    else:
                        body = ""
                    params = _parse_form(body)
                    ssid = params.get("ssid", "").strip()
                    pw   = params.get("password", "")

                    if ssid:
                        conn.send(_PAGE_OK.encode())
                        conn.close()
                        config.save_wifi_creds(ssid, pw)
                        saved = True
                        break
                    else:
                        conn.send(_PAGE_ERR.encode())
                else:
                    conn.send(_PAGE.encode())

            except Exception as e:
                print("wifi_setup: request error —", e)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    finally:
        srv.close()
        ap.active(False)

    if saved:
        display.show_status("Saved! Rebooting...", display.GREEN)
        utime.sleep_ms(1000)
        machine.reset()

    display.show_status("WiFi setup cancelled", display.AMBER)
    utime.sleep_ms(1500)
    return False
