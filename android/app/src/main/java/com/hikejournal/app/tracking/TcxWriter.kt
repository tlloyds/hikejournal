package com.hikejournal.app.tracking

import java.io.File
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.time.Instant
import java.util.Locale

internal object TcxDocument {
    fun render(snapshot: TrackingSnapshot): String = buildString {
        append("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        append(
            "<TrainingCenterDatabase " +
                "xmlns=\"http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2\" " +
                "xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" " +
                "xsi:schemaLocation=\"http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2 " +
                "http://www.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd\">\n",
        )
        append("  <Activities>\n")
        append("    <Activity Sport=\"Other\">\n")
        append("      <Id>${utc(snapshot.startedAtEpochMs)}</Id>\n")
        append("      <Lap StartTime=\"${utc(snapshot.startedAtEpochMs)}\">\n")
        append("        <TotalTimeSeconds>${decimal(snapshot.activeElapsedMs / 1_000.0)}</TotalTimeSeconds>\n")
        append("        <DistanceMeters>${decimal(snapshot.distanceMeters)}</DistanceMeters>\n")
        append("        <Intensity>Active</Intensity>\n")
        snapshot.routeSegments.filter { it.size >= 2 }.forEach { segment ->
            append("        <Track>\n")
            segment.forEach { point ->
                append("          <Trackpoint>\n")
                append("            <Time>${utc(point.fixEpochMs)}</Time>\n")
                append("            <Position>\n")
                append("              <LatitudeDegrees>${decimal(point.latitude)}</LatitudeDegrees>\n")
                append("              <LongitudeDegrees>${decimal(point.longitude)}</LongitudeDegrees>\n")
                append("            </Position>\n")
                point.altitudeMeters?.takeIf(Double::isFinite)?.let { altitude ->
                    append("            <AltitudeMeters>${decimal(altitude)}</AltitudeMeters>\n")
                }
                append("          </Trackpoint>\n")
            }
            append("        </Track>\n")
        }
        append("        <TriggerMethod>Manual</TriggerMethod>\n")
        append("      </Lap>\n")
        append("    </Activity>\n")
        append("  </Activities>\n")
        append("</TrainingCenterDatabase>\n")
    }

    private fun utc(epochMs: Long): String = Instant.ofEpochMilli(epochMs).toString()

    private fun decimal(value: Double): String = String.format(Locale.US, "%.6f", value)
}

internal class TcxWriter(private val directory: File) {
    fun write(snapshot: TrackingSnapshot): File {
        check(snapshot.routeSegments.any { it.size >= 2 }) {
            "At least one route segment with two points is required for TCX"
        }
        directory.mkdirs()
        check(directory.isDirectory) { "Unable to create tracking route directory" }
        val destination = File(directory, "${snapshot.sessionId}.tcx")
        val temporary = File(directory, ".${snapshot.sessionId}.${System.nanoTime()}.tmp")
        try {
            temporary.outputStream().bufferedWriter(Charsets.UTF_8).use { writer ->
                writer.write(TcxDocument.render(snapshot))
            }
            try {
                Files.move(
                    temporary.toPath(),
                    destination.toPath(),
                    StandardCopyOption.REPLACE_EXISTING,
                    StandardCopyOption.ATOMIC_MOVE,
                )
            } catch (_: AtomicMoveNotSupportedException) {
                Files.move(
                    temporary.toPath(),
                    destination.toPath(),
                    StandardCopyOption.REPLACE_EXISTING,
                )
            }
        } finally {
            if (temporary.exists()) temporary.delete()
        }
        return destination
    }
}
