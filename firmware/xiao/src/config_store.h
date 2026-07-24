// Persistent configuration storage via ESP32 NVS (non-volatile storage).
// Wraps Arduino Preferences under namespace "cyclops_cfg", separate from
// NimBLE's "nimble_bond" namespace.
//
// Singleton: ConfigStore::instance()
// Keys: wifi_ssid, wifi_pass, llm_key, assistant_name, assistant_role,
//       timezone, language, consent, config_done
#ifndef CONFIG_STORE_H
#define CONFIG_STORE_H
#include <cstdint>
#include <cstring>
#include <cstdio>
namespace cyclops {

struct ConfigStore {
    static ConfigStore& instance();

    bool load();
    bool save();
    void reset();
    bool is_configured() const { return config_done_; }

    const char* wifi_ssid() const { return wifi_ssid_; }
    void set_wifi_ssid(const char* v) { copy(wifi_ssid_, v, sizeof(wifi_ssid_)); }
    const char* wifi_pass() const { return wifi_pass_; }
    void set_wifi_pass(const char* v) { copy(wifi_pass_, v, sizeof(wifi_pass_)); }
    const char* llm_key() const { return llm_key_; }
    void set_llm_key(const char* v) { copy(llm_key_, v, sizeof(llm_key_)); }
    const char* assistant_name() const { return assistant_name_; }
    void set_assistant_name(const char* v) { copy(assistant_name_, v, sizeof(assistant_name_)); }
    const char* assistant_role() const { return assistant_role_; }
    void set_assistant_role(const char* v) { copy(assistant_role_, v, sizeof(assistant_role_)); }
    const char* timezone() const { return timezone_; }
    void set_timezone(const char* v) { copy(timezone_, v, sizeof(timezone_)); }
    const char* language() const { return language_; }
    void set_language(const char* v) { copy(language_, v, sizeof(language_)); }
    bool consent() const { return consent_; }
    void set_consent(bool v) { consent_ = v; }

private:
    ConfigStore() = default;
    void copy(char* dst, const char* src, size_t sz) {
        size_t n = src ? strlen(src) : 0;
        if (n >= sz) n = sz - 1;
        memcpy(dst, src ? src : "", n);
        dst[n] = 0;
    }
    char wifi_ssid_[64]{};
    char wifi_pass_[64]{};
    char llm_key_[128]{};
    char assistant_name_[32]{};
    char assistant_role_[256]{};
    char timezone_[64]{};
    char language_[16]{};
    bool consent_ = false;
    bool config_done_ = false;
};

}  // namespace cyclops
#endif  // CONFIG_STORE_H
