package com.cyclops.companion

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo

/**
 * Dev-only config injector: lets `adb shell am broadcast` push brain URL /
 * provider / api key into SharedPreferences without hand-typing them into
 * Settings after every fresh install (an uninstall — e.g. a signing-key
 * change — wipes app data, unlike `adb install -r`).
 *
 * Not exported (other apps can't trigger it); also refuses to run on a
 * non-debuggable build as a second guard, since `adb shell am broadcast`
 * can still target non-exported receivers by explicit component name.
 *
 * Usage: scripts/push_env_config.sh (reads /home/gio/.env, fires this).
 *   adb shell am broadcast -n com.cyclops.companion/.ConfigReceiver \
 *     -a com.cyclops.companion.SET_CONFIG \
 *     --es url "http://192.168.1.50:8080" \
 *     --es provider "omniroute" \
 *     --es api_key "sk-..."
 */
class ConfigReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val debuggable = (context.applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE) != 0
        if (!debuggable) return

        val prefs = context.getSharedPreferences("cyclops", Context.MODE_PRIVATE)
        prefs.edit().apply {
            intent.getStringExtra("url")?.let { putString("url", it) }
            intent.getStringExtra("provider")?.let { putString("provider", it) }
            intent.getStringExtra("api_key")?.let { putString("api_key", it) }
            intent.getStringExtra("local_endpoint")?.let { putString("local_endpoint", it) }
            apply()
        }
        intent.getStringExtra("url")?.let { CyclopsApi.baseUrl = it }
    }
}
