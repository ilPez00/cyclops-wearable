package com.cyclops.companion

import android.app.Application
import com.google.android.material.color.DynamicColors

/**
 * Opts the whole app into Material 3 dynamic color (API 31+). On older
 * devices the static brand tokens in colors.xml are used as the fallback.
 */
class CyclopsApp : Application() {
    override fun onCreate() {
        super.onCreate()
        DynamicColors.applyToActivitiesIfAvailable(this)
    }
}
