package com.cyclops.companion

import android.content.Context
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.appbar.MaterialToolbar

/** setPadding()/LayoutParams take pixels, not dp — this codebase's
 *  programmatic screens have historically passed raw ints assuming dp
 *  (e.g. setPadding(32,32,32,32)), which renders smaller than intended on
 *  any screen denser than mdpi. Use this to convert real dp values. */
fun Int.dp(ctx: Context): Int = (this * ctx.resources.displayMetrics.density).toInt()

/**
 * Every non-MainActivity screen wants the same thing: a visible title and a
 * working back affordance. Theme.Cyclops's base theme is NoActionBar, so
 * setting Activity.title alone renders nothing — several screens (Feed,
 * Vision, Experiences) shipped with no on-screen back button as a result,
 * relying entirely on the OS back gesture. This wraps any content view in a
 * MaterialToolbar with up-navigation, as a two-line addition regardless of
 * whether the screen's content is an XML layout or built programmatically.
 */
abstract class BaseActivity : AppCompatActivity() {

    /** Call instead of setContentView() — wraps [child] under a toolbar
     *  showing [screenTitle], with the up arrow finishing the activity. */
    protected fun setContentViewWithToolbar(child: View, screenTitle: String) {
        val toolbar = MaterialToolbar(this).apply {
            setBackgroundColor(getColor(R.color.cyclops_surface))
            setTitleTextColor(getColor(R.color.cyclops_primary))
        }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            addView(toolbar, LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
            addView(child, LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
        }
        setContentView(root)
        setSupportActionBar(toolbar)
        supportActionBar?.apply {
            title = screenTitle
            setDisplayHomeAsUpEnabled(true)
        }
    }

    override fun onSupportNavigateUp(): Boolean {
        onBackPressedDispatcher.onBackPressed()
        return true
    }

    protected fun Int.dp(): Int = dp(this@BaseActivity)
}
