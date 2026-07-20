package com.hikejournal.app.data.local

import android.content.Context
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
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

    @Query("SELECT * FROM pending_operations ORDER BY createdAt ASC")
    fun observeAll(): Flow<List<PendingOperationEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(operation: PendingOperationEntity)

    @Query("DELETE FROM pending_operations WHERE id = :id")
    suspend fun delete(id: String)

    @Query("DELETE FROM pending_operations WHERE kind = :kind AND entityId = :entityId AND state = 'queued'")
    suspend fun deleteQueued(kind: String, entityId: String)

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

    @Query("UPDATE pending_operations SET state = 'queued', lastError = NULL, updatedAt = :updatedAt WHERE state = 'needs_attention'")
    suspend fun retryAttention(updatedAt: Long)
}

@Database(entities = [PendingOperationEntity::class], version = 1, exportSchema = true)
abstract class OfflineDatabase : RoomDatabase() {
    abstract fun operations(): PendingOperationDao

    companion object {
        @Volatile private var instance: OfflineDatabase? = null

        fun get(context: Context): OfflineDatabase = instance ?: synchronized(this) {
            instance ?: Room.databaseBuilder(
                context.applicationContext,
                OfflineDatabase::class.java,
                "hikejournal-field.db",
            ).build().also { instance = it }
        }
    }
}
