package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class CompanionConfigTest {
    @Test
    fun `parses current config while ignoring blank capabilities`() {
        val config = parseCompanionConfig(
            json = """{
                "web_url":"https://journal.example.com/",
                "api_version":"0.6.28",
                "capabilities":["offline_sync","", "hike_deletion", "offline_sync"],
                "contract_version":"1",
                "compatibility":{
                    "minimum_android_version":"0.6.20",
                    "recommended_android_version":"0.6.29"
                }
            }""",
            fallbackWebUrl = "https://fallback.example.com",
        )

        assertEquals("https://journal.example.com", config.webUrl)
        assertEquals("0.6.28", config.apiVersion)
        assertEquals(setOf("offline_sync", "hike_deletion"), config.capabilities)
        assertEquals("1", config.contractVersion)
        assertEquals("0.6.20", config.minimumAndroidVersion)
        assertEquals("0.6.29", config.recommendedAndroidVersion)
    }

    @Test
    fun `older config safely keeps the existing web fallback`() {
        val config = parseCompanionConfig(
            json = "{}",
            fallbackWebUrl = "http://192.168.0.157:8505/",
        )

        assertEquals("http://192.168.0.157:8505", config.webUrl)
        assertNull(config.apiVersion)
        assertEquals(emptySet<String>(), config.capabilities)
        assertNull(config.contractVersion)
        assertNull(config.minimumAndroidVersion)
        assertNull(config.recommendedAndroidVersion)
    }

    @Test
    fun `invalid server web address cannot replace a valid fallback`() {
        val config = parseCompanionConfig(
            json = """{"web_url":"javascript:alert(1)"}""",
            fallbackWebUrl = "https://journal.example.com",
        )

        assertEquals("https://journal.example.com", config.webUrl)
    }

    @Test
    fun `server web address with query cannot replace a valid fallback`() {
        val config = parseCompanionConfig(
            json = """{"web_url":"https://journal.example.com?unexpected=true"}""",
            fallbackWebUrl = "https://fallback.example.com",
        )

        assertEquals("https://fallback.example.com", config.webUrl)
    }

    @Test
    fun `nullable compatibility values remain absent`() {
        val config = parseCompanionConfig(
            json = """{
                "contract_version":null,
                "compatibility":{
                    "minimum_android_version":null,
                    "recommended_android_version":""
                }
            }""",
            fallbackWebUrl = "https://fallback.example.com",
        )

        assertNull(config.contractVersion)
        assertNull(config.minimumAndroidVersion)
        assertNull(config.recommendedAndroidVersion)
    }
}
