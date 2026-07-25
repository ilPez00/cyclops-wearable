// Captive WiFi configuration portal for Cyclops XIAO ESP32-S3 Sense.
// Adapted from XIAO_OpenAI_complete_voice_and_vision_assistant/config_portal.h
// (see dev/xiao_s3 for original).
//
// Activated on first boot (ConfigStore !is_configured()) or factory reset
// (hold BTN_A + BTN_B at boot). User connects phone to "Cyclops-Setup-XXXX",
// fills SSID/password/API key in browser, saves to NVS via ConfigStore,
// then device restarts into normal operation.
//
// Guarded by -DCONFIG_PORTAL=1. When undefined, all calls are no-ops.
#pragma once
#include <Arduino.h>
#ifdef CONFIG_PORTAL
#include <WebServer.h>
#include <DNSServer.h>
#include <WiFi.h>
#endif
#include "config_store.h"

static constexpr int CONFIG_PORTAL_DNS_PORT = 53;
static constexpr const char* CONFIG_PORTAL_PASSWORD = "cyclops123";

// ---------------------------------------------------------------------------
// HTML page — captive portal form (minimal, no OpenAI-specific fields)
// ---------------------------------------------------------------------------
static const char CONFIG_HTML[] PROGMEM =
"<!DOCTYPE html>"
"<html lang='en'><head>"
"<meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1.0'>"
"<title>Cyclops Setup</title>"
"<style>"
"*{margin:0;padding:0;box-sizing:border-box}"
"body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;"
"background:#1a1a2e;min-height:100vh;display:flex;justify-content:center;align-items:center;padding:20px}"
".card{background:#16213e;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,.5);"
"max-width:480px;width:100%;padding:32px;color:#e0e0e0}"
"h1{color:#0f3460;font-size:24px;margin-bottom:4px;text-align:center}"
".sub{color:#888;font-size:13px;text-align:center;margin-bottom:24px}"
"label{display:block;color:#ccc;font-weight:600;font-size:13px;margin-bottom:6px;margin-top:16px}"
"input{width:100%;padding:10px 14px;border:1px solid #333;border-radius:8px;"
"font-size:15px;background:#1a1a2e;color:#e0e0e0;transition:border .2s}"
"input:focus{outline:none;border-color:#e94560}"
".hint{font-size:11px;color:#666;margin-top:4px}"
"button{width:100%;margin-top:24px;padding:12px;background:#e94560;color:#fff;"
"border:none;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer;"
"transition:opacity .2s}button:hover{opacity:.85}"
".status{margin-top:16px;padding:12px;border-radius:8px;text-align:center;font-size:13px;display:none}"
".status.ok{background:#1b4332;color:#95d5b2;display:block}"
".status.err{background:#3d0c11;color:#ef8a92;display:block}"
"</style></head><body>"
"<div class='card'>"
"<h1>Cyclops</h1>"
"<p class='sub'>Wearable HUD — First-Time Setup</p>"
"<form id='f' method='POST' action='/save'>"
"<label>WiFi Network (SSID)</label>"
"<input type='text' name='ssid' placeholder='Enter SSID' value='%SSID%' required>"
"<label>WiFi Password</label>"
"<input type='password' name='pass' placeholder='%PASS_PLACEHOLDER%'>"
"<div class='hint'>%PASS_HINT%</div>"
"<label>LLM API Key</label>"
"<input type='password' name='apikey' placeholder='%KEY_PLACEHOLDER%'>"
"<div class='hint'>%KEY_HINT%</div>"
"<button type='submit'>Save &amp; Reboot</button>"
"</form>"
"<div id='status' class='status'></div>"
"</div>"
"<script>"
"document.getElementById('f').onsubmit=function(e){"
"var s=document.getElementById('status');"
"var ssid=document.getElementById('ssid').value.trim();"
"if(!ssid){s.className='status err';s.textContent='SSID is required';e.preventDefault();return}"
"var b=this.querySelector('button');b.disabled=true;b.textContent='Saving...'};"
"</script></body></html>";

// ---------------------------------------------------------------------------
// The success page (served after save + before reboot)
// ---------------------------------------------------------------------------
static const char CONFIG_SAVED_HTML[] PROGMEM =
"<!DOCTYPE html><html><head><meta charset='UTF-8'>"
"<meta name='viewport' content='width=device-width,initial-scale=1.0'>"
"<title>Saved!</title>"
"<style>body{font-family:sans-serif;display:flex;justify-content:center;"
"align-items:center;min-height:100vh;background:#1a1a2e;color:#e0e0e0}"
".box{background:#16213e;padding:40px;border-radius:16px;text-align:center}"
"h1{color:#95d5b2}div{font-size:48px;margin-bottom:16px}</style></head>"
"<body><div class='box'><div>&#10003;</div>"
"<h1>Configuration Saved</h1><p>Device restarting...</p>"
"<p>Reconnect to your WiFi and the app.</p></div></body></html>";

// ---------------------------------------------------------------------------
// Portal globals (guarded by CONFIG_PORTAL)
// ---------------------------------------------------------------------------
#ifdef CONFIG_PORTAL

static WebServer* g_portal_server = nullptr;
static DNSServer g_portal_dns;
static bool g_portal_active = false;
static uint32_t g_portal_start_ms = 0;
static constexpr uint32_t CONFIG_PORTAL_TIMEOUT_MS = 60000;  // 60 s then auto-bypass

static String portal_html() {
    String h = FPSTR(CONFIG_HTML);
    auto& s = cyclops::ConfigStore::instance();
    bool first = !s.is_configured();
    String cur_ssid = s.wifi_ssid();
    h.replace("%SSID%", cur_ssid.length() > 0 ? cur_ssid : "");
    if (first) {
        h.replace("%PASS_PLACEHOLDER%", "Enter WiFi password");
        h.replace("%PASS_HINT%", "Required for first setup");
        h.replace("%KEY_PLACEHOLDER%", "Enter your LLM API key");
        h.replace("%KEY_HINT%", "Required for first setup");
    } else {
        h.replace("%PASS_PLACEHOLDER%", "Leave blank to keep current");
        h.replace("%PASS_HINT%", "Leave blank to keep current password");
        h.replace("%KEY_PLACEHOLDER%", "Leave blank to keep current");
        h.replace("%KEY_HINT%", "Leave blank to keep current API key");
    }
    return h;
}

static void handle_portal_root() {
    g_portal_server->send(200, "text/html", portal_html());
}

static void handle_portal_save() {
    if (g_portal_server->method() != HTTP_POST) {
        g_portal_server->send(405, "text/plain", "Method Not Allowed");
        return;
    }
    auto& store = cyclops::ConfigStore::instance();
    String ssid = g_portal_server->arg("ssid");
    String pass = g_portal_server->arg("pass");
    String apikey = g_portal_server->arg("apikey");
    ssid.trim(); pass.trim(); apikey.trim();
    if (ssid.length() == 0) {
        g_portal_server->send(400, "text/plain", "SSID is required");
        return;
    }
    // Merge: if user left a field blank, keep the stored value
    store.set_wifi_ssid(ssid.c_str());
    if (pass.length() > 0) store.set_wifi_pass(pass.c_str());
    if (apikey.length() > 0) store.set_llm_key(apikey.c_str());
    store.save();
    g_portal_server->send(200, "text/html", FPSTR(CONFIG_SAVED_HTML));
    delay(2000);
    ESP.restart();
}

static void handle_portal_not_found() {
    g_portal_server->sendHeader("Location", "/", true);
    g_portal_server->send(302, "text/plain", "");
}

#endif  // CONFIG_PORTAL

// ---------------------------------------------------------------------------
// Public API — called from main.cpp
// ---------------------------------------------------------------------------
static inline void config_portal_start() {
#ifdef CONFIG_PORTAL
    if (g_portal_active) return;
    Serial.println("[portal] Starting captive portal...");
    String mac = WiFi.macAddress();
    mac.replace(":", "");
    String ssid = "Cyclops-Setup-" + mac.substring(6);
    WiFi.mode(WIFI_AP_STA);
    WiFi.softAP(ssid.c_str(), CONFIG_PORTAL_PASSWORD);
    IPAddress ip = WiFi.softAPIP();
    Serial.printf("[portal] AP SSID: %s  IP: %s\n", ssid.c_str(), ip.toString().c_str());
    g_portal_dns.start(CONFIG_PORTAL_DNS_PORT, "*", ip);
    g_portal_server = new WebServer(80);
    g_portal_server->on("/", HTTP_GET, handle_portal_root);
    g_portal_server->on("/save", HTTP_POST, handle_portal_save);
    g_portal_server->onNotFound(handle_portal_not_found);
    g_portal_server->begin();
    g_portal_start_ms = millis();
    g_portal_active = true;
    Serial.println("[portal] Ready. Connect phone to " + ssid + " (" + String(CONFIG_PORTAL_TIMEOUT_MS/1000) + "s timeout)");
#endif
}

static inline void config_portal_tick() {
#ifdef CONFIG_PORTAL
    if (!g_portal_active) return;
    g_portal_dns.processNextRequest();
    g_portal_server->handleClient();
#endif
}

static inline bool config_portal_timeout() {
#ifdef CONFIG_PORTAL
    return g_portal_active && (millis() - g_portal_start_ms >= CONFIG_PORTAL_TIMEOUT_MS);
#else
    return false;
#endif
}

static inline void config_portal_stop() {
#ifdef CONFIG_PORTAL
    if (!g_portal_active) return;
    g_portal_server->stop();
    delete g_portal_server;
    g_portal_server = nullptr;
    WiFi.softAPdisconnect(true);
    WiFi.mode(WIFI_STA);
    g_portal_active = false;
    Serial.println("[portal] Stopped.");
#endif
}
