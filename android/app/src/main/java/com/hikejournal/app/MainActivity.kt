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
        handleInatIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleInatIntent(intent)
    }

    private fun handleInatIntent(intent: Intent?) {
        if (intent?.data?.scheme != "hikejournal" || intent.data?.host != "inat") return
        viewModel.completeInatConnection(intent.data?.getQueryParameter("status") == "connected")
    }
}
