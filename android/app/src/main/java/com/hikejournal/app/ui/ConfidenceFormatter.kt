package com.hikejournal.app.ui

import kotlin.math.roundToInt

internal fun usesFractionalConfidenceScale(values: Iterable<Double?>): Boolean =
    values.filterNotNull().none { it > 1.0 }

internal fun formatConfidencePercent(value: Double, usesFractionalScale: Boolean): String {
    if (!value.isFinite()) return "0%"
    val percentage = if (usesFractionalScale) value * 100 else value
    return "${percentage.coerceIn(0.0, 100.0).roundToInt()}%"
}
