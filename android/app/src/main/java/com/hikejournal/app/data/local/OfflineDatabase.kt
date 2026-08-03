package com.hikejournal.app.data.local

import android.content.Context
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.Update
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "pending_operations")
data class PendingOperationEntity(
    @PrimaryKey val id: String,
    val kind: String,
    val entityId: String,
    val parentId: String?,
    val payloadJson: String,
    val localFilePath: String?,
    val contentType: String?,
    val fileName: String?,
    val state: String,
    val attemptCount: Int,
    val createdAt: Long,
    val updatedAt: Long,
    val lastError: String?,
)

@Dao
interface PendingOperationDao {
    @Query("SELECT * FROM pending_operations ORDER BY createdAt ASC")
    suspend fun listAll(): List<PendingOperationEntity>

    @Query(
        "SELECT * FROM pending_operations WHERE entityId = :hikeId OR parentId = :hikeId " +
            "ORDER BY createdAt ASC",
    )
    suspend fun listForHike(hikeId: String): List<PendingOperationEntity>

    @Query("SELECT * FROM pending_operations ORDER BY createdAt ASC")
    fun observeAll(): Flow<List<PendingOperationEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(operation: PendingOperationEntity)

    @Query("DELETE FROM pending_operations WHERE id = :id")
    suspend fun delete(id: String)

    @Query(
        "DELETE FROM pending_operations WHERE kind = :kind AND entityId = :entityId " +
            "AND state IN ('queued', 'needs_attention')",
    )
    suspend fun deleteReplaceable(kind: String, entityId: String)

    @Query("SELECT * FROM pending_operations WHERE kind = :kind AND entityId = :entityId LIMIT 1")
    suspend fun find(kind: String, entityId: String): PendingOperationEntity?

    @Query(
        "UPDATE pending_operations SET state = :state, attemptCount = :attemptCount, " +
            "updatedAt = :updatedAt, lastError = :lastError WHERE id = :id",
    )
    suspend fun updateState(
        id: String,
        state: String,
        attemptCount: Int,
        updatedAt: Long,
        lastError: String?,
    )

    @Query("UPDATE pending_operations SET state = 'queued', attemptCount = 0, lastError = NULL, updatedAt = :updatedAt WHERE state = 'needs_attention'")
    suspend fun retryAttention(updatedAt: Long)

    @Query("SELECT * FROM pending_operations WHERE state = 'needs_attention' ORDER BY createdAt ASC")
    suspend fun listAttention(): List<PendingOperationEntity>

    @Query("DELETE FROM pending_operations WHERE id = :id AND state = 'needs_attention'")
    suspend fun discardAttention(id: String)
}

@Entity(
    tableName = "tracking_sessions",
    indices = [
        Index(value = ["hikeId"], unique = true),
        Index(value = ["activeSlot"], unique = true),
        Index(value = ["status"]),
    ],
)
data class TrackingSessionEntity(
    @PrimaryKey val sessionId: String,
    val hikeId: String,
    val activeSlot: Int?,
    val status: String,
    val startedAtEpochMs: Long,
    val startedAtElapsedRealtimeMs: Long,
    val hikeDate: String,
    val bootCount: Int,
    val activeElapsedMs: Long,
    val activeSinceElapsedRealtimeMs: Long?,
    val distanceMeters: Double,
    val currentSegment: Int,
    val segmentStartPending: Boolean,
    val nextPointSequence: Long,
    val lastFixEpochMs: Long?,
    val lastFixElapsedRealtimeNanos: Long?,
    val lastAccuracyMeters: Float?,
    val finishedAtEpochMs: Long?,
    val generatedTcxPath: String?,
    val recoveryReason: String?,
    val error: String?,
    val updatedAtEpochMs: Long,
)

@Entity(
    tableName = "tracking_points",
    primaryKeys = ["sessionId", "sequence"],
    foreignKeys = [
        ForeignKey(
            entity = TrackingSessionEntity::class,
            parentColumns = ["sessionId"],
            childColumns = ["sessionId"],
            onDelete = ForeignKey.CASCADE,
        ),
    ],
    indices = [Index(value = ["sessionId", "segment", "sequence"])],
)
data class TrackingPointEntity(
    val sessionId: String,
    val sequence: Long,
    val segment: Int,
    val latitude: Double,
    val longitude: Double,
    val altitudeMeters: Double?,
    val accuracyMeters: Float,
    val fixEpochMs: Long,
    val fixElapsedRealtimeNanos: Long,
    val distanceFromPreviousMeters: Double,
)

@Dao
interface TrackingDao {
    @Query("SELECT * FROM tracking_sessions WHERE activeSlot = 1 LIMIT 1")
    fun observeActiveSession(): Flow<TrackingSessionEntity?>

    @Query("SELECT * FROM tracking_sessions WHERE activeSlot = 1 LIMIT 1")
    suspend fun activeSession(): TrackingSessionEntity?

    @Query("SELECT * FROM tracking_sessions WHERE sessionId = :sessionId LIMIT 1")
    suspend fun session(sessionId: String): TrackingSessionEntity?

    @Query("SELECT * FROM tracking_sessions WHERE hikeId = :hikeId AND status = 'FINISHED' LIMIT 1")
    suspend fun finishedSession(hikeId: String): TrackingSessionEntity?

    @Query("SELECT * FROM tracking_sessions WHERE status = 'FINISHED' AND (:hikeId IS NULL OR hikeId = :hikeId)")
    suspend fun finishedSessions(hikeId: String?): List<TrackingSessionEntity>

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertSession(session: TrackingSessionEntity)

    @Update
    suspend fun updateSession(session: TrackingSessionEntity)

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertPoint(point: TrackingPointEntity)

    @Query("SELECT * FROM tracking_points WHERE sessionId = :sessionId ORDER BY sequence ASC")
    fun observePoints(sessionId: String): Flow<List<TrackingPointEntity>>

    @Query("SELECT * FROM tracking_points WHERE sessionId = :sessionId ORDER BY sequence ASC")
    suspend fun points(sessionId: String): List<TrackingPointEntity>

    @Query("SELECT * FROM tracking_points WHERE sessionId = :sessionId ORDER BY sequence DESC LIMIT 1")
    suspend fun lastPoint(sessionId: String): TrackingPointEntity?

    @Query("DELETE FROM tracking_sessions WHERE status = 'FINISHED' AND (:hikeId IS NULL OR hikeId = :hikeId)")
    suspend fun clearFinished(hikeId: String?): Int

    @Query("DELETE FROM tracking_sessions WHERE sessionId = :sessionId AND activeSlot = 1")
    suspend fun discardActive(sessionId: String): Int
}

@Database(
    entities = [
        PendingOperationEntity::class,
        TrackingSessionEntity::class,
        TrackingPointEntity::class,
    ],
    version = 2,
    exportSchema = true,
)
abstract class OfflineDatabase : RoomDatabase() {
    abstract fun operations(): PendingOperationDao
    abstract fun tracking(): TrackingDao

    companion object {
        @Volatile private var instance: OfflineDatabase? = null

        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS `tracking_sessions` (
                        `sessionId` TEXT NOT NULL,
                        `hikeId` TEXT NOT NULL,
                        `activeSlot` INTEGER,
                        `status` TEXT NOT NULL,
                        `startedAtEpochMs` INTEGER NOT NULL,
                        `startedAtElapsedRealtimeMs` INTEGER NOT NULL,
                        `hikeDate` TEXT NOT NULL,
                        `bootCount` INTEGER NOT NULL,
                        `activeElapsedMs` INTEGER NOT NULL,
                        `activeSinceElapsedRealtimeMs` INTEGER,
                        `distanceMeters` REAL NOT NULL,
                        `currentSegment` INTEGER NOT NULL,
                        `segmentStartPending` INTEGER NOT NULL,
                        `nextPointSequence` INTEGER NOT NULL,
                        `lastFixEpochMs` INTEGER,
                        `lastFixElapsedRealtimeNanos` INTEGER,
                        `lastAccuracyMeters` REAL,
                        `finishedAtEpochMs` INTEGER,
                        `generatedTcxPath` TEXT,
                        `recoveryReason` TEXT,
                        `error` TEXT,
                        `updatedAtEpochMs` INTEGER NOT NULL,
                        PRIMARY KEY(`sessionId`)
                    )
                    """.trimIndent(),
                )
                db.execSQL(
                    "CREATE UNIQUE INDEX IF NOT EXISTS `index_tracking_sessions_hikeId` " +
                        "ON `tracking_sessions` (`hikeId`)",
                )
                db.execSQL(
                    "CREATE UNIQUE INDEX IF NOT EXISTS `index_tracking_sessions_activeSlot` " +
                        "ON `tracking_sessions` (`activeSlot`)",
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS `index_tracking_sessions_status` " +
                        "ON `tracking_sessions` (`status`)",
                )
                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS `tracking_points` (
                        `sessionId` TEXT NOT NULL,
                        `sequence` INTEGER NOT NULL,
                        `segment` INTEGER NOT NULL,
                        `latitude` REAL NOT NULL,
                        `longitude` REAL NOT NULL,
                        `altitudeMeters` REAL,
                        `accuracyMeters` REAL NOT NULL,
                        `fixEpochMs` INTEGER NOT NULL,
                        `fixElapsedRealtimeNanos` INTEGER NOT NULL,
                        `distanceFromPreviousMeters` REAL NOT NULL,
                        PRIMARY KEY(`sessionId`, `sequence`),
                        FOREIGN KEY(`sessionId`) REFERENCES `tracking_sessions`(`sessionId`)
                            ON UPDATE NO ACTION ON DELETE CASCADE
                    )
                    """.trimIndent(),
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS `index_tracking_points_sessionId_segment_sequence` " +
                        "ON `tracking_points` (`sessionId`, `segment`, `sequence`)",
                )
            }
        }

        fun get(context: Context): OfflineDatabase = instance ?: synchronized(this) {
            instance ?: Room.databaseBuilder(
                context.applicationContext,
                OfflineDatabase::class.java,
                "hikejournal-field.db",
            ).addMigrations(MIGRATION_1_2)
                .build()
                .also { instance = it }
        }
    }
}
