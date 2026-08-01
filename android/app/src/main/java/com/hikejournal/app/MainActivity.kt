package com.hikejournal.app

import android.os.Bundle
import android.content.Intent
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import com.hikejournal.app.ui.HikeJournalApp
import com.hikejournal.app.ui.theme.HikeJournalTheme

class MainActivity : ComponentActivity() {
    private val viewModel: AppViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            HikeJournalTheme {
                HikeJournalApp(viewModel)
            }
        }
        handleAppIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleAppIntent(intent)
    }

    private fun handleAppIntent(intent: Intent?) {
        val data = intent?.data ?: return
        if (data.scheme != "hikejournal") return
        when (data.host) {
            "inat" -> viewModel.completeInatConnection(data.getQueryParameter("status") == "connected")
            "tracking" -> viewModel.openTrackingFromNotification(confirmEnd = data.path == "/end")
            else -> return
        }
        // A notification/deep-link is a one-shot event. Clearing it prevents rotations and other
        // Activity recreation from replaying Pause/End navigation.
        intent.data = null
        intent.action = null
        setIntent(intent)
    }
}
