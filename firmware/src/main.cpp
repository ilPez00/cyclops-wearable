// Cyclops firmware dispatcher.
// PlatformIO compiles this as the single src/main.cpp. The active target is
// selected by a build flag (-DCYCLOPS_XIAO) set per env in platformio.ini.
// (The Arduino/AVR target was retired — the desktop HUD simulator
// shells/hud_sim.py renders the same wire frames for development.)
#ifdef CYCLOPS_XIAO
#include "../xiao/src/main.cpp"
#endif
#if !defined(CYCLOPS_XIAO)
#error "Define CYCLOPS_XIAO in build_flags"
#endif
