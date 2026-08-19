package com.hikejournal.app.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.nio.charset.StandardCharsets
import java.security.KeyStore
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import org.json.JSONObject

data class AuthAccount(
    val subject: String,
    val email: String,
    val displayName: String,
    val pictureUrl: String = "",
)

data class MobileSession(
    val accessToken: String,
    val refreshToken: String,
    val account: AuthAccount,
)

internal class AuthPreferences(context: Context) {
    private val appContext = context.applicationContext
    private val preferences = appContext.getSharedPreferences(PreferencesName, Context.MODE_PRIVATE)
    private val associatedData = "${appContext.packageName}:$KeyAlias".toByteArray(StandardCharsets.UTF_8)

    fun deviceId(): String {
        preferences.getString(DeviceIdKey, null)?.takeIf(String::isNotBlank)?.let { return it }
        return UUID.randomUUID().toString().also {
            preferences.edit().putString(DeviceIdKey, it).apply()
        }
    }

    @Synchronized
    fun session(): MobileSession? {
        val ciphertext = preferences.getString(SessionCiphertextKey, null) ?: return null
        val iv = preferences.getString(SessionIvKey, null) ?: return null
        val json = runCatching {
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
        }.getOrNull() ?: return null
        return runCatching { parseSession(json) }.getOrNull()
    }

    @Synchronized
    fun save(session: MobileSession) {
        val json = JSONObject()
            .put("access_token", session.accessToken)
            .put("refresh_token", session.refreshToken)
            .put(
                "account",
                JSONObject()
                    .put("subject", session.account.subject)
                    .put("email", session.account.email)
                    .put("display_name", session.account.displayName)
                    .put("picture_url", session.account.pictureUrl),
            )
            .toString()
        val cipher = Cipher.getInstance(CipherTransformation)
        cipher.init(Cipher.ENCRYPT_MODE, existingKey() ?: createKey())
        cipher.updateAAD(associatedData)
        val encrypted = cipher.doFinal(json.toByteArray(StandardCharsets.UTF_8))
        preferences.edit()
            .putString(SessionCiphertextKey, Base64.encodeToString(encrypted, Base64.NO_WRAP))
            .putString(SessionIvKey, Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .apply()
    }

    @Synchronized
    fun clear() {
        preferences.edit().remove(SessionCiphertextKey).remove(SessionIvKey).apply()
    }

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
        const val PreferencesName = "hikejournal_auth"
        const val DeviceIdKey = "device_id"
        const val SessionCiphertextKey = "session_ciphertext_v1"
        const val SessionIvKey = "session_iv_v1"
        const val KeyAlias = "hikejournal_google_session_v1"
        const val AndroidKeyStore = "AndroidKeyStore"
        const val CipherTransformation = "AES/GCM/NoPadding"
        const val GcmTagBits = 128

        fun parseSession(json: String): MobileSession {
            val root = JSONObject(json)
            val account = root.getJSONObject("account")
            return MobileSession(
                accessToken = root.getString("access_token"),
                refreshToken = root.getString("refresh_token"),
                account = AuthAccount(
                    subject = account.getString("subject"),
                    email = account.getString("email"),
                    displayName = account.optString("display_name", account.getString("email")),
                    pictureUrl = account.optString("picture_url"),
                ),
            )
        }
    }
}
