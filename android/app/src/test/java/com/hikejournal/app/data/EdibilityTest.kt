package com.hikejournal.app.data

import java.time.Instant
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class EdibilityTest {
    private val afterRead = Instant.parse("2026-11-15T12:00:00Z")

    private fun referenceJson() = JSONObject(
        """
        {
          "taxon_id":42,
          "scientific_name":"Example taxon",
          "rank":"species",
          "dataset_version":"fixture-v2",
          "food_use_status":"documented",
          "toxicity_status":"unknown",
          "review_status":"source_matched",
          "documented_parts":[],
          "sources":[{
            "title":"Fixture checklist",
            "version":"2",
            "url":"https://example.test/checklist",
            "attribution":"Example Author",
            "license":"CC BY 4.0",
            "license_url":"https://creativecommons.org/licenses/by/4.0/"
          }],
          "expires_at":"2026-11-16T12:00:00+00:00"
        }
        """.trimIndent(),
    )

    private fun tagJson() = JSONObject()
        .put("observation_id", "test-tag")
        .put("taxon_id", 42)
        .put("scientific_name", "Example taxon")
        .put("status", "confirmed")
        .put("iconic_taxon_name", "Plantae")
        .put("edibility", referenceJson())

    private fun photoWith(vararg tags: JSONObject): Photo {
        val photo = JSONObject().put("id", "photo")
            .put(EdibilityReadStartedAt, 100)
            .put("species", JSONArray(tags.toList()))
        val hike = JSONObject().put("id", "hike").put("photos", JSONArray().put(photo))
        return parseHike(hike.toString()).photos.single()
    }

    @Test
    fun `reference round trips through journal JSON and old servers fall back`() {
        val photo = photoWith(tagJson())
        val (_, reference) = photo.foodUseTags(true, 0, afterRead).single()
        assertEquals("fixture-v2", reference.datasetVersion)
        assertEquals("Fixture checklist", reference.sources.single().title)
        assertEquals(FoodUseStatus.Documented, reference.foodUse)
        assertEquals(ToxicityStatus.Unknown, reference.toxicity)
        assertTrue(reference.documentedParts.isEmpty())
        assertNull(parseSpecies("""{"key":"taxon:42"}""").edibility)
        assertNull(parseSpecies("""{"key":"taxon:42","edibility":null}""").edibility)
        assertTrue(photoWith(tagJson().put("edibility", JSONObject.NULL)).foodUseTags(true, 0, afterRead).isEmpty())
    }

    @Test
    fun `unknown enums fail closed and a reference needs a traceable source`() {
        val unknown = referenceJson().put("food_use_status", "new_value").put("toxicity_status", "new_value")
        assertNull(parseEdibility(unknown)?.indicator)
        assertNull(parseEdibility(referenceJson().put("review_status", "needs_review")))
        assertNull(parseEdibility(referenceJson().put("sources", JSONArray())))
        assertNull(parseEdibility(referenceJson().put("expires_at", "invalid")))
    }

    @Test
    fun `part evidence requires a parsed citation and does not collapse edible and toxic parts`() {
        val payload = referenceJson().put("part_evidence", JSONArray("""
            [
              {"part":"Leaves","kind":"toxic","source_url":"https://example.test/checklist"},
              {"part":"Flowers","kind":"edible","source_url":"https://example.test/checklist"},
              {"part":"Fruit","kind":"edible","source_url":"https://example.test/unlisted"}
            ]
        """.trimIndent()))
        val reference = checkNotNull(parseEdibility(payload))
        assertEquals(listOf("Leaves", "Flowers"), reference.partEvidence.map { it.part })
        assertEquals(listOf(PlantPartEvidenceKind.Toxic, PlantPartEvidenceKind.Edible), reference.partEvidence.map { it.kind })
        assertEquals(reference.sources.single(), reference.partEvidence.first().source)
    }

    @Test
    fun `only exact current confirmed visible tags receive indicators`() {
        val good = tagJson().put("observation_id", "confirmed")
        val pending = tagJson().put("status", "pending")
        val reassigned = tagJson().put("taxon_id", 43)
        val nameMismatch = tagJson().put("scientific_name", "Another taxon")
        val fungus = tagJson().put("iconic_taxon_name", "Fungi")
        val candidate = tagJson().put("observation_id", JSONObject.NULL)
        val unsupportedRank = tagJson().put("edibility", referenceJson().put("rank", "genus"))
        val photo = photoWith(good, pending, reassigned, nameMismatch, fungus, candidate, unsupportedRank)
        assertEquals("confirmed", photo.foodUseTags(true, 0, afterRead).single().first.observationId)
        assertTrue(photo.foodUseTags(false, 0, afterRead).isEmpty())
        assertTrue(photo.copy(syncState = "queued").foodUseTags(true, 0, afterRead).isEmpty())
        assertTrue(photo.copy(species = emptyList()).foodUseTags(true, 0, afterRead).isEmpty())
        assertTrue(photo.foodUseTags(true, 99, afterRead.plusSeconds(86_400)).isEmpty())
        assertTrue(photo.foodUseTags(true, 100, afterRead).isEmpty())
        assertTrue(photo.copy(edibilityReadStartedAt = 101).foodUseTags(true, 100, afterRead).isNotEmpty())
    }

    @Test
    fun `warnings take precedence and the food filter retains documented hazards and conflict`() {
        val warning = checkNotNull(parseEdibility(referenceJson()
            .put("food_use_status", "disputed")
            .put("has_documented_food_use", true)
            .put("evidence_conflict", true)
            .put("toxicity_status", "documented_concern")))
        assertEquals(FoodUseIndicator.Toxicity, warning.indicator)
        val conflict = warning.copy(toxicity = ToxicityStatus.Unknown)
        assertEquals(FoodUseIndicator.Conflict, conflict.indicator)
        assertTrue(conflict.hasDocumentedFoodUse)
        val conditional = checkNotNull(parseEdibility(referenceJson().put("food_use_status", "conditional")))
        assertEquals(FoodUseIndicator.Conditional, conditional.indicator)
        val base = parseSpecies("""{"key":"taxon:42","taxon_id":42,"scientific_name":"Example taxon","rank":"species"}""")
        val noData = base.copy(key = "unknown")
        val records = listOf(
            base.copy(edibility = warning.copy(expiresAt = Instant.MAX)),
            noData,
            base.copy(key = "other", taxonId = 43, edibility = conditional.copy(expiresAt = Instant.MAX)),
        )
        assertEquals(records, filterSpeciesByFoodUse(records, false))
        assertEquals(listOf(records.first()), filterSpeciesByFoodUse(records, true))
        assertFalse(noData.edibilityReferenceEnabled)
    }
}
