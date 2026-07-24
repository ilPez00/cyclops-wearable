// Host-gate tests for ConfigStore (in-memory host stub).
// Compile: g++ -std=c++17 -I shared/include -I lib/cyclops_shared/include \
//                 -I xiao/src shared/test_config_store.cpp \
//                 xiao/src/config_store.cpp -o /tmp/cyclops_test_config_store
#include "config_store.h"
#include <cstdio>
#include <cstring>
#include <cassert>
#include <string>

static int failures = 0;
#define TEST(name) do { printf("  %-44s ", name); } while(0)
#define PASS() do { printf("PASS\n"); } while(0)
#define FAIL(msg) do { printf("FAIL: %s\n", msg); ++failures; } while(0)
#define ASSERT(cond, msg) do { if (!(cond)) { FAIL(msg); return; } } while(0)

static void test_defaults() {
    TEST("defaults are empty/false");
    auto& s = cyclops::ConfigStore::instance();
    s.reset();
    ASSERT(strlen(s.wifi_ssid()) == 0, "wifi_ssid should be empty");
    ASSERT(strlen(s.wifi_pass()) == 0, "wifi_pass should be empty");
    ASSERT(strlen(s.llm_key()) == 0, "llm_key should be empty");
    ASSERT(strlen(s.assistant_name()) == 0, "assistant_name should be empty");
    ASSERT(strlen(s.assistant_role()) == 0, "assistant_role should be empty");
    ASSERT(strlen(s.timezone()) == 0, "timezone should be empty");
    ASSERT(strlen(s.language()) == 0, "language should be empty");
    ASSERT(!s.consent(), "consent should be false");
    ASSERT(!s.is_configured(), "config_done should be false");
    PASS();
}

static void test_set_and_read() {
    TEST("set values readable without save");
    auto& s = cyclops::ConfigStore::instance();
    s.reset();
    s.set_wifi_ssid("MyNet");
    ASSERT(strcmp(s.wifi_ssid(), "MyNet") == 0, "wifi_ssid mismatch");
    ASSERT(strlen(s.wifi_pass()) == 0, "wifi_pass should still be empty");
    PASS();
}

static void test_save_load_roundtrip() {
    TEST("save then load preserves all values");
    auto& s = cyclops::ConfigStore::instance();
    s.reset();
    s.set_wifi_ssid("MyHomeWiFi");
    s.set_wifi_pass("secret123");
    s.set_llm_key("sk-test-key-abc123");
    s.set_assistant_name("Cyclops");
    s.set_assistant_role("You are a helpful wearable assistant.");
    s.set_timezone("America/New_York");
    s.set_language("en");
    s.set_consent(true);
    ASSERT(s.save(), "save should succeed");
    // Clear cache to simulate fresh load (but NOT reset — that erases NVS)
    s.set_wifi_ssid("xxx"); s.set_wifi_pass("xxx"); s.set_llm_key("xxx");
    s.set_assistant_name("xxx"); s.set_assistant_role("xxx");
    s.set_timezone("xxx"); s.set_language("xx"); s.set_consent(false);
    ASSERT(s.load(), "load should succeed");
    ASSERT(strcmp(s.wifi_ssid(), "MyHomeWiFi") == 0, "wifi_ssid mismatch");
    ASSERT(strcmp(s.wifi_pass(), "secret123") == 0, "wifi_pass mismatch");
    ASSERT(strcmp(s.llm_key(), "sk-test-key-abc123") == 0, "llm_key mismatch");
    ASSERT(strcmp(s.assistant_name(), "Cyclops") == 0, "assistant_name mismatch");
    ASSERT(strcmp(s.assistant_role(), "You are a helpful wearable assistant.") == 0, "assistant_role mismatch");
    ASSERT(strcmp(s.timezone(), "America/New_York") == 0, "timezone mismatch");
    ASSERT(strcmp(s.language(), "en") == 0, "language mismatch");
    ASSERT(s.consent(), "consent should be true");
    ASSERT(!s.is_configured(), "config_done should still be false");
    PASS();
}

static void test_reset_clears_everything() {
    TEST("reset clears cache and backing store");
    auto& s = cyclops::ConfigStore::instance();
    s.reset();
    s.set_wifi_ssid("toClear");
    s.set_wifi_pass("toClear");
    s.save();
    s.reset();
    ASSERT(strlen(s.wifi_ssid()) == 0, "wifi_ssid should be empty after reset");
    ASSERT(strlen(s.wifi_pass()) == 0, "wifi_pass should be empty after reset");
    ASSERT(!s.consent(), "consent should be false after reset");
    ASSERT(!s.is_configured(), "config_done should be false after reset");
    // load after reset should also return empty (backing store was cleared)
    s.load();
    ASSERT(strlen(s.wifi_ssid()) == 0, "wifi_ssid should be empty after reset+load");
    PASS();
}

static void test_truncation() {
    TEST("long values are truncated to buffer size");
    auto& s = cyclops::ConfigStore::instance();
    s.reset();
    std::string long_str(200, 'x');
    s.set_llm_key(long_str.c_str());
    ASSERT(strlen(s.llm_key()) < 200, "llm_key should be truncated");
    ASSERT(strlen(s.llm_key()) == 127, "llm_key should be 127 chars (128-1)");
    PASS();
}

int main() {
    printf("ConfigStore host-gate tests\n");
    test_defaults();
    test_set_and_read();
    test_save_load_roundtrip();
    test_reset_clears_everything();
    test_truncation();
    printf("\n%d failures\n", failures);
    return failures;
}
