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

val Moss = Color(0xFF324223)
val MossSoft = Color(0xFF465A32)
val Fern = Color(0xFFAECE76)
val Trail = Color(0xFFD17D42)
val Parchment = Color(0xFFF5F1E7)
val Paper = Color(0xFFF4ECEB)
val Ink = Color(0xFF293520)
// Secondary copy and labels must remain legible in bright outdoor conditions.
val InkMuted = Color(0xFF56614F)
val TrailText = Color(0xFF97512A)
val TrailBadge = Color(0xFFA6552D)
val FernText = Color(0xFF506A3D)
val Line = Color(0xFFD8D4C6)
val Lichen = Color(0xFFE2E8D4)

private val DisplayFamily = FontFamily(
    Font(R.font.cormorant_garamond_400, weight = FontWeight.Normal),
    Font(R.font.cormorant_garamond_600, weight = FontWeight.SemiBold),
    Font(R.font.cormorant_garamond_700, weight = FontWeight.Bold),
)

// Quicksand is named in the supplied Illustrator file. Static instances preserve
// its real weights instead of mapping every style to a variable font's light default.
val BrandFamily = FontFamily(
    Font(R.font.quicksand_400, weight = FontWeight.Normal),
    Font(R.font.quicksand_500, weight = FontWeight.Medium),
    Font(R.font.quicksand_600, weight = FontWeight.SemiBold),
    Font(R.font.quicksand_700, weight = FontWeight.Bold),
)
private val BodyFamily = BrandFamily

private val HikeTypography = Typography(
    displayLarge = TextStyle(fontFamily = DisplayFamily, fontWeight = FontWeight.SemiBold, fontSize = 56.sp, lineHeight = 60.sp),
    displayMedium = TextStyle(fontFamily = DisplayFamily, fontWeight = FontWeight.SemiBold, fontSize = 44.sp, lineHeight = 48.sp),
    displaySmall = TextStyle(fontFamily = DisplayFamily, fontWeight = FontWeight.SemiBold, fontSize = 36.sp, lineHeight = 40.sp),
    headlineLarge = TextStyle(fontFamily = DisplayFamily, fontWeight = FontWeight.SemiBold, fontSize = 36.sp, lineHeight = 40.sp),
    headlineMedium = TextStyle(fontFamily = DisplayFamily, fontWeight = FontWeight.SemiBold, fontSize = 30.sp, lineHeight = 35.sp),
    headlineSmall = TextStyle(fontFamily = DisplayFamily, fontWeight = FontWeight.SemiBold, fontSize = 25.sp, lineHeight = 30.sp),
    titleLarge = TextStyle(fontFamily = BodyFamily, fontWeight = FontWeight.SemiBold, fontSize = 20.sp, lineHeight = 26.sp),
    titleMedium = TextStyle(fontFamily = BodyFamily, fontWeight = FontWeight.SemiBold, fontSize = 17.sp, lineHeight = 23.sp),
    titleSmall = TextStyle(fontFamily = BodyFamily, fontWeight = FontWeight.SemiBold, fontSize = 15.sp, lineHeight = 21.sp),
    bodyLarge = TextStyle(fontFamily = BodyFamily, fontWeight = FontWeight.Normal, fontSize = 17.sp, lineHeight = 25.sp),
    bodyMedium = TextStyle(fontFamily = BodyFamily, fontWeight = FontWeight.Normal, fontSize = 15.sp, lineHeight = 22.sp),
    bodySmall = TextStyle(fontFamily = BodyFamily, fontWeight = FontWeight.Normal, fontSize = 14.sp, lineHeight = 20.sp),
    labelLarge = TextStyle(fontFamily = BodyFamily, fontWeight = FontWeight.Bold, fontSize = 15.sp, lineHeight = 20.sp),
    labelMedium = TextStyle(fontFamily = BodyFamily, fontWeight = FontWeight.SemiBold, fontSize = 13.sp, lineHeight = 18.sp, letterSpacing = 0.35.sp),
    labelSmall = TextStyle(fontFamily = BodyFamily, fontWeight = FontWeight.SemiBold, fontSize = 12.sp, lineHeight = 16.sp, letterSpacing = 0.75.sp),
)

private val HikeColors = lightColorScheme(
    primary = Moss,
    onPrimary = Paper,
    primaryContainer = Lichen,
    onPrimaryContainer = Moss,
    secondary = Trail,
    onSecondary = Paper,
    secondaryContainer = Lichen,
    onSecondaryContainer = Moss,
    tertiary = MossSoft,
    onTertiary = Paper,
    tertiaryContainer = Lichen,
    onTertiaryContainer = Moss,
    surfaceTint = Moss,
    surfaceContainer = Paper,
    surfaceContainerHigh = Parchment,
    surfaceContainerHighest = Lichen,
    surfaceContainerLow = Parchment,
    surfaceContainerLowest = Color.White,
    surfaceBright = Color.White,
    surfaceDim = Color(0xFFE7E4DA),
    outlineVariant = Line,
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
