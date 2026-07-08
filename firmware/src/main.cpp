// Cyclops firmware dispatcher.
// PlatformIO compiles this as the single src/main.cpp. The active target is
// selected by a build flag (-DCYCLOPS_ARDUINO / -DCYCLOPS_XIAO) set per env in
// platformio.ini, so each board builds its own real firmware from one tree.
#ifdef CYCLOPS_ARDUINO
#include "../arduino/src/main.cpp"
#endif
#ifdef CYCLOPS_XIAO
#include "../xiao/src/main.cpp"
#endif
#if !defined(CYCLOPS_ARDUINO) && !defined(CYCLOPS_XIAO)
#error "Define CYCLOPS_ARDUINO or CYCLOPS_XIAO in build_flags"
#endif
