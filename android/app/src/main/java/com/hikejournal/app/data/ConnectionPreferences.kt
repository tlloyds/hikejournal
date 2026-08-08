package com.hikejournal.app.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.nio.charset.StandardCharsets
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Keeps the connection address backward-compatible while moving an explicitly entered pairing
 * key out of plaintext SharedPreferences. The legacy value is retained only when a device's
 * keystore is unavailable, so a storage-provider edge case cannot lock an existing personal app
 * out of its companion.
 */
internal class ConnectionPreferences(context: Context) {
    private val appContext = context.applicationContext
    private val preferences = appContext.getSharedPreferences(PreferencesName, Context.MODE_PRIVATE)
    private val associatedData = "${appContext.packageName}:$KeyAlias".toByteArray(StandardCharsets.UTF_8)

    fun serverUrl(defaultValue: String): String = preferences
        .getString(ServerUrlKey, defaultValue)
        ?.trim()
        ?.trimEnd('/')
        ?: defaultValue

    fun setServerUrl(value: String) {
        preferences.edit().putString(ServerUrlKey, value.trim().trimEnd('/')).apply()
    }

    @Synchronized
    fun pairingKey(defaultValue: String): String {
        decryptPairingKey()?.let { return it.trim() }
        val legacy = preferences.getString(LegacyPairingKey, null)?.trim()
        if (!legacy.isNullOrBlank()) {
            // Best-effort in-place migration. Encryption success removes the plaintext value;
            // failure leaves the legacy value untouched so an existing installation still works.
            encryptAndStore(legacy)
            return legacy
        }
        return defaultValue.trim()
    }

    @Synchronized
    fun setPairingKey(value: String) {
        val clean = value.trim()
        if (clean.isBlank()) {
            preferences.edit()
                .remove(EncryptedPairingKey)
                .remove(EncryptedPairingIv)
                .remove(LegacyPairingKey)
                .apply()
            return
        }
        if (!encryptAndStore(clean)) {
            // Never let a decryptable stale ciphertext win over the newly entered
            // compatibility fallback on the next read.
            preferences.edit()
                .remove(EncryptedPairingKey)
                .remove(EncryptedPairingIv)
                .putString(LegacyPairingKey, clean)
                .apply()
        }
    }

    private fun decryptPairingKey(): String? {
        val ciphertext = preferences.getString(EncryptedPairingKey, null) ?: return null
        val iv = preferences.getString(EncryptedPairingIv, null) ?: return null
        return runCatching {
            val cipher = Cipher.getInstance(CipherTransformation)
            cipher.init(
                Cipher.DECRYPT_MODE,
                existingKey() ?: return@runCatching null,
                GCMParameterSpec(GcmTagBits, Base64.decode(iv, Base64.NO_WRAP)),
            )
            cipher.updateAAD(associatedData)
            String(
                cipher.doFinal(Base64.decode(ciphertext, Base64.NO_WRAP)),
                StandardCharsets.UTF_8,
            )
        }.getOrNull()
    }

    private fun encryptAndStore(value: String): Boolean = runCatching {
        val cipher = Cipher.getInstance(CipherTransformation)
        cipher.init(Cipher.ENCRYPT_MODE, existingKey() ?: createKey())
        cipher.updateAAD(associatedData)
        val encrypted = cipher.doFinal(value.toByteArray(StandardCharsets.UTF_8))
        preferences.edit()
            .putString(EncryptedPairingKey, Base64.encodeToString(encrypted, Base64.NO_WRAP))
            .putString(EncryptedPairingIv, Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .remove(LegacyPairingKey)
            .apply()
        true
    }.getOrDefault(false)

    private fun existingKey(): SecretKey? {
        val keyStore = KeyStore.getInstance(AndroidKeyStore).apply { load(null) }
        return keyStore.getKey(KeyAlias, null) as? SecretKey
    }

    private fun createKey(): SecretKey {
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, AndroidKeyStore)
        generator.init(
            KeyGenParameterSpec.Builder(
                KeyAlias,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build(),
        )
        return generator.generateKey()
    }

    private companion object {
        const val PreferencesName = "hikejournal"
        const val ServerUrlKey = "server_url"
        const val LegacyPairingKey = "pairing_key"
        const val EncryptedPairingKey = "pairing_key_encrypted_v1"
        const val EncryptedPairingIv = "pairing_key_iv_v1"
        const val KeyAlias = "hikejournal_pairing_key_v1"
        const val AndroidKeyStore = "AndroidKeyStore"
        const val CipherTransformation = "AES/GCM/NoPadding"
        const val GcmTagBits = 128
    }
}
