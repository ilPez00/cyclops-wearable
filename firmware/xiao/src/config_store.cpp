// See config_store.h.
#include "config_store.h"
#ifdef ARDUINO
#include <Preferences.h>
static Preferences prefs;
static const char* NVS_NS = "cyclops_cfg";
namespace cyclops {
ConfigStore& ConfigStore::instance() {
    static ConfigStore s;
    return s;
}
bool ConfigStore::load() {
    if (!prefs.begin(NVS_NS, true)) return false;
    auto get = [](Preferences& p, const char* key, char* dst, size_t sz) {
        String v = p.getString(key, "");
        size_t n = v.length();
        if (n >= sz) n = sz - 1;
        memcpy(dst, v.c_str(), n);
        dst[n] = 0;
    };
    get(prefs, "wifi_ssid", wifi_ssid_, sizeof(wifi_ssid_));
    get(prefs, "wifi_pass", wifi_pass_, sizeof(wifi_pass_));
    get(prefs, "llm_key", llm_key_, sizeof(llm_key_));
    get(prefs, "asst_name", assistant_name_, sizeof(assistant_name_));
    get(prefs, "asst_role", assistant_role_, sizeof(assistant_role_));
    get(prefs, "timezone", timezone_, sizeof(timezone_));
    get(prefs, "language", language_, sizeof(language_));
    consent_ = prefs.getBool("consent", false);
    config_done_ = prefs.getBool("config_done", false);
    prefs.end();
    return true;
}
bool ConfigStore::save() {
    if (!prefs.begin(NVS_NS, false)) return false;
    prefs.putString("wifi_ssid", wifi_ssid_);
    prefs.putString("wifi_pass", wifi_pass_);
    prefs.putString("llm_key", llm_key_);
    prefs.putString("asst_name", assistant_name_);
    prefs.putString("asst_role", assistant_role_);
    prefs.putString("timezone", timezone_);
    prefs.putString("language", language_);
    prefs.putBool("consent", consent_);
    prefs.putBool("config_done", config_done_);
    prefs.end();
    return true;
}
void ConfigStore::reset() {
    if (!prefs.begin(NVS_NS, false)) return;
    prefs.clear();
    prefs.end();
    wifi_ssid_[0] = 0; wifi_pass_[0] = 0; llm_key_[0] = 0;
    assistant_name_[0] = 0; assistant_role_[0] = 0;
    timezone_[0] = 0; language_[0] = 0;
    consent_ = false; config_done_ = false;
}
}  // namespace cyclops
#else
// Host (g++) build: in-memory singleton simulating NVS, no real hardware needed.
#include <cstdlib>
#include <map>
#include <string>
namespace cyclops {
// Persistent backing store — survives across save/load cycles on the same
// singleton instance. "Reset" (factory reset) clears it.
static std::map<std::string, std::string>& nvs_store() {
    static std::map<std::string, std::string> m;
    return m;
}
ConfigStore& ConfigStore::instance() {
    static ConfigStore s;
    return s;
}
static void load_key(const std::string& key, char* dst, size_t sz) {
    auto& kv = nvs_store();
    auto it = kv.find(key);
    if (it != kv.end()) {
        size_t n = it->second.size();
        if (n >= sz) n = sz - 1;
        memcpy(dst, it->second.c_str(), n);
        dst[n] = 0;
    } else {
        dst[0] = 0;
    }
}
bool ConfigStore::load() {
    load_key("wifi_ssid", wifi_ssid_, sizeof(wifi_ssid_));
    load_key("wifi_pass", wifi_pass_, sizeof(wifi_pass_));
    load_key("llm_key", llm_key_, sizeof(llm_key_));
    load_key("asst_name", assistant_name_, sizeof(assistant_name_));
    load_key("asst_role", assistant_role_, sizeof(assistant_role_));
    load_key("timezone", timezone_, sizeof(timezone_));
    load_key("language", language_, sizeof(language_));
    consent_ = nvs_store()["consent"] == "1";
    config_done_ = nvs_store()["config_done"] == "1";
    return true;
}
bool ConfigStore::save() {
    auto& kv = nvs_store();
    kv["wifi_ssid"] = wifi_ssid_;
    kv["wifi_pass"] = wifi_pass_;
    kv["llm_key"] = llm_key_;
    kv["asst_name"] = assistant_name_;
    kv["asst_role"] = assistant_role_;
    kv["timezone"] = timezone_;
    kv["language"] = language_;
    kv["consent"] = consent_ ? "1" : "0";
    kv["config_done"] = config_done_ ? "1" : "0";
    return true;
}
void ConfigStore::reset() {
    nvs_store().clear();
    wifi_ssid_[0]=0; wifi_pass_[0]=0; llm_key_[0]=0;
    assistant_name_[0]=0; assistant_role_[0]=0;
    timezone_[0]=0; language_[0]=0;
    consent_=false; config_done_=false;
}
}  // namespace cyclops
#endif
