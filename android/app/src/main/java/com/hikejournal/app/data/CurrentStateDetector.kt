package com.hikejournal.app.data

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.Geocoder
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Build
import android.os.Bundle
import android.os.CancellationSignal
import android.os.Looper
import androidx.core.content.ContextCompat
import java.util.Locale
import kotlin.coroutines.resume
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull

class StateDetectionException(message: String) : IllegalStateException(message)

suspend fun detectCurrentUsState(context: Context): String {
    val appContext = context.applicationContext
    if (
        appContext.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED &&
        appContext.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED
    ) {
        throw StateDetectionException("Allow location once, or choose your state from the list.")
    }
    val location = currentLocation(appContext)
        ?: throw StateDetectionException("Your current location is not available yet. Choose your state from the list.")
    if (!Geocoder.isPresent()) {
        throw StateDetectionException("State lookup is not available on this device. Choose your state from the list.")
    }
    val stateCode = withContext(Dispatchers.IO) {
        @Suppress("DEPRECATION")
        val address = Geocoder(appContext, Locale.US)
            .getFromLocation(location.latitude, location.longitude, 1)
            ?.firstOrNull()
        usStateCodeForName(address?.adminArea)
            ?: usStateCodeForName(address?.subAdminArea)
    }
    return stateCode
        ?: throw StateDetectionException("HikeJournal could not match that location to a U.S. state. Choose one from the list.")
}

@SuppressLint("MissingPermission")
private suspend fun currentLocation(context: Context): Location? {
    val manager = context.getSystemService(LocationManager::class.java)
    val hasFineLocation =
        context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
    val providers = buildList {
        add(LocationManager.NETWORK_PROVIDER)
        if (hasFineLocation) add(LocationManager.GPS_PROVIDER)
        add(LocationManager.PASSIVE_PROVIDER)
    }.filter { provider -> runCatching { manager.isProviderEnabled(provider) }.getOrDefault(false) }
    val cached = providers
        .mapNotNull { provider -> runCatching { manager.getLastKnownLocation(provider) }.getOrNull() }
        .filter { location -> System.currentTimeMillis() - location.time <= 24 * 60 * 60 * 1_000L }
        .maxByOrNull(Location::getTime)
    if (cached != null) return cached
    val provider = providers.firstOrNull() ?: return null
    return withTimeoutOrNull(12_000) {
        suspendCancellableCoroutine { continuation ->
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                val cancellation = CancellationSignal()
                continuation.invokeOnCancellation { cancellation.cancel() }
                manager.getCurrentLocation(
                    provider,
                    cancellation,
                    ContextCompat.getMainExecutor(context),
                ) { location ->
                    if (continuation.isActive) continuation.resume(location)
                }
            } else {
                val listener = object : LocationListener {
                    override fun onLocationChanged(location: Location) {
                        manager.removeUpdates(this)
                        if (continuation.isActive) continuation.resume(location)
                    }

                    override fun onProviderDisabled(provider: String) {
                        manager.removeUpdates(this)
                        if (continuation.isActive) continuation.resume(null)
                    }

                    override fun onProviderEnabled(provider: String) = Unit

                    @Deprecated("Deprecated in Android")
                    override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) = Unit
                }
                continuation.invokeOnCancellation { manager.removeUpdates(listener) }
                @Suppress("DEPRECATION")
                manager.requestSingleUpdate(provider, listener, Looper.getMainLooper())
            }
        }
    }
}
