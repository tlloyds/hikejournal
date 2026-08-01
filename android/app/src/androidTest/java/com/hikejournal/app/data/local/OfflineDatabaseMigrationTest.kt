package com.hikejournal.app.data.local

import androidx.room.testing.MigrationTestHelper
import androidx.sqlite.db.framework.FrameworkSQLiteOpenHelperFactory
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.IOException
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class OfflineDatabaseMigrationTest {
    @get:Rule
    val helper = MigrationTestHelper(
        InstrumentationRegistry.getInstrumentation(),
        OfflineDatabase::class.java,
        emptyList(),
        FrameworkSQLiteOpenHelperFactory(),
    )

    @Test
    @Throws(IOException::class)
    fun migration1To2PreservesQueueAndCreatesTrackingTables() {
        helper.createDatabase(TEST_DATABASE, 1).apply {
            execSQL(
                """
                INSERT INTO pending_operations (
                    id, kind, entityId, parentId, payloadJson, localFilePath, contentType,
                    fileName, state, attemptCount, createdAt, updatedAt, lastError
                ) VALUES ('op', 'create_hike', 'hike', NULL, '{}', NULL, NULL, NULL,
                    'queued', 0, 1, 1, NULL)
                """.trimIndent(),
            )
            close()
        }

        helper.runMigrationsAndValidate(
            TEST_DATABASE,
            2,
            true,
            OfflineDatabase.MIGRATION_1_2,
        ).use { database ->
            database.query("SELECT COUNT(*) FROM pending_operations").use { cursor ->
                cursor.moveToFirst()
                assertEquals(1, cursor.getInt(0))
            }
            database.query(
                "SELECT name FROM sqlite_master WHERE type = 'table' " +
                    "AND name IN ('tracking_sessions', 'tracking_points')",
            ).use { cursor ->
                assertEquals(2, cursor.count)
            }
        }
    }

    companion object {
        private const val TEST_DATABASE = "offline-migration-test"
    }
}
