package com.hikejournal.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import com.hikejournal.app.R

val Moss = Color(0xFF183A2D)
val MossSoft = Color(0xFF315844)
val Fern = Color(0xFF76916D)
val Trail = Color(0xFFD17D42)
val Parchment = Color(0xFFF4F0E5)
val Paper = Color(0xFFFFFCF3)
val Ink = Color(0xFF1D241F)
// Secondary copy and labels must remain legible in bright outdoor conditions.
val InkMuted = Color(0xFF526057)
val TrailText = Color(0xFF9B4D27)
val FernText = Color(0xFF4D6A50)
val Line = Color(0xFFD8D3C7)
val Lichen = Color(0xFFDCE5D6)

private val DisplayFamily = FontFamily(
    Font(R.font.cormorant_garamond, weight = FontWeight.Normal),
    Font(R.font.cormorant_garamond, weight = FontWeight.SemiBold),
    Font(R.font.cormorant_garamond, weight = FontWeight.Bold),
)

private val BodyFamily = FontFamily(
    Font(R.font.source_sans_3, weight = FontWeight.Normal),
    Font(R.font.source_sans_3, weight = FontWeight.Medium),
    Font(R.font.source_sans_3, weight = FontWeight.SemiBold),
    Font(R.font.source_sans_3, weight = FontWeight.Bold),
)

private val HikeTypography = Typography(
    displayLarge = TextStyle(fontFamily = DisplayFamily, fontWeight = FontWeight.SemiBold, fontSize = 56.sp, lineHeight = 54.sp),
    displayMedium = TextStyle(fontFamily = DisplayFamily, fontWeight = FontWeight.SemiBold, fontSize = 44.sp, lineHeight = 44.sp),
    headlineLarge = TextStyle(fontFamily = DisplayFamily, fontWeight = FontWeight.SemiBold, fontSize = 36.sp, lineHeight = 38.sp),
    headlineMedium = TextStyle(fontFamily = DisplayFamily, fontWeight = FontWeight.SemiBold, fontSize = 30.sp, lineHeight = 32.sp),
    headlineSmall = TextStyle(fontFamily = DisplayFamily, fontWeight = FontWeight.SemiBold, fontSize = 25.sp, lineHeight = 28.sp),
    titleLarge = TextStyle(fontFamily = BodyFamily, fontWeight = FontWeight.SemiBold, fontSize = 20.sp, lineHeight = 25.sp),
    titleMedium = TextStyle(fontFamily = BodyFamily, fontWeight = FontWeight.SemiBold, fontSize = 17.sp, lineHeight = 22.sp),
    bodyLarge = TextStyle(fontFamily = BodyFamily, fontWeight = FontWeight.Normal, fontSize = 17.sp, lineHeight = 25.sp),
    bodyMedium = TextStyle(fontFamily = BodyFamily, fontWeight = FontWeight.Normal, fontSize = 15.sp, lineHeight = 22.sp),
    labelLarge = TextStyle(fontFamily = BodyFamily, fontWeight = FontWeight.SemiBold, fontSize = 15.sp, lineHeight = 20.sp),
    labelMedium = TextStyle(fontFamily = BodyFamily, fontWeight = FontWeight.SemiBold, fontSize = 12.sp, letterSpacing = 0.8.sp),
    labelSmall = TextStyle(fontFamily = BodyFamily, fontWeight = FontWeight.SemiBold, fontSize = 11.sp, letterSpacing = 1.1.sp),
)

private val HikeColors = lightColorScheme(
    primary = Moss,
    onPrimary = Paper,
    primaryContainer = Lichen,
    onPrimaryContainer = Moss,
    secondary = Trail,
    onSecondary = Paper,
    background = Parchment,
    onBackground = Ink,
    surface = Paper,
    onSurface = Ink,
    surfaceVariant = Color(0xFFE9E5D9),
    onSurfaceVariant = InkMuted,
    outline = Line,
    error = Color(0xFF9E3F34),
)

@Composable
fun HikeJournalTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = HikeColors,
        typography = HikeTypography,
        content = content,
    )
}
