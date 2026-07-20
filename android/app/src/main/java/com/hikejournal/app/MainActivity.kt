package com.hikejournal.app

import android.os.Bundle
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
    }
}
