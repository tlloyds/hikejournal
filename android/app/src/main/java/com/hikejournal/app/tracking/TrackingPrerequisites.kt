package com.hikejournal.app.tracking

import android.Manifest
import android.app.NotificationManager
import android.content.Context
import android.content.pm.PackageManager
import android.location.LocationManager
import android.os.Build
import androidx.core.content.ContextCompat

object TrackingPrerequisites {
    fun check(context: Context): TrackingPrerequisiteState {
        val fineLocation = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_FINE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED
        val notificationManager = ContextCompat.getSystemService(context, NotificationManager::class.java)
        val notifications = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.POST_NOTIFICATIONS,
            ) == PackageManager.PERMISSION_GRANTED && notificationManager?.areNotificationsEnabled() != false
        } else {
            notificationManager?.areNotificationsEnabled() != false
        }
        val locationManager = ContextCompat.getSystemService(context, LocationManager::class.java)
        val locationEnabled = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            locationManager?.isLocationEnabled == true
        } else {
            locationManager?.isProviderEnabled(LocationManager.GPS_PROVIDER) == true ||
                locationManager?.isProviderEnabled(LocationManager.NETWORK_PROVIDER) == true
        }
        return TrackingPrerequisiteState(
            fineLocationGranted = fineLocation,
            notificationsGranted = notifications,
            locationEnabled = locationEnabled,
        )
    }
}
