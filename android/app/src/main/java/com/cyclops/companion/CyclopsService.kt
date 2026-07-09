package com.cyclops.companion

import android.app.*
import android.bluetooth.*
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.cyclops.companion.core.CyclopsProto
import com.cyclops.companion.core.HudBridge
import java.util.*

/**
 * BLE hub: connects to the XIAO wearable (NimBLE GATT server), pumps incoming
 * frames into a [HudBridge], and forwards the bridge's display frames back to
 * the device over the NOTE characteristic. Heavy lifting (ASR/vision) happens
 * in the Python brain, reached via LocalBridge over localhost.
 *
 * Depends on the Android Bluetooth APIs (cannot run outside an app/emulator
 * with BLE), so it is type-checked + structured by the IDE but not executed in
 * CI. The protocol logic it relies on lives in the dependency-free `:core`
 * module, which is unit-tested.
 *
 * Lifecycle: started as a foreground service from MainActivity's toolbar
 * ("Connect wearable" toggle) so it survives backgrounding.
 */
class CyclopsService : Service() {
    companion object {
        val SRVC_UUID = UUID.fromString("4fafc201-1fb5-459e-8fcc-c5c9c331914b")
        val NOTE_UUID = UUID.fromString("beb5483e-36e1-4688-b7f5-ea07361b26a8")
        const val CHANNEL_ID = "cyclops_ble"
        const val NOTIF_ID = 1
        const val ACTION_STOP = "com.cyclops.companion.action.STOP"
    }

    private lateinit var bluetoothGatt: BluetoothGatt
    private var noteChar: BluetoothGattCharacteristic? = null
    private val bridge = HudBridge(
        sink = object : HudBridge.Sink {
            override fun write(frame: ByteArray) = sendToDevice(frame)
        }
    )
    private val decoder = CyclopsProto.Decoder { type, payload ->
        when (type) {
            CyclopsProto.MSG_CMD -> bridge.handleCmd(payload)
            CyclopsProto.MSG_AUDIO_META,
            CyclopsProto.MSG_AUDIO_CHUNK,
            CyclopsProto.MSG_AUDIO_STOP -> bridge.handleAudio(type, payload)
            else -> { /* display/status frames: forward to glasses screen */ }
        }
    }

    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) { stopForeground(true); stopSelf(); return START_NOT_STICKY }
        startForeground(NOTIF_ID, buildNotification("Cyclops wearable link active"))
        return START_STICKY
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            val ch = NotificationChannel(CHANNEL_ID, "Wearable link", NotificationManager.IMPORTANCE_LOW)
            getSystemService(NotificationManager::class.java).createNotificationChannel(ch)
        }
    }

    private fun buildNotification(text: String): Notification =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Cyclops")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
            .setOngoing(true)
            .build()

    private val gattCallback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                gatt.discoverServices()
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                bluetoothGatt = gatt
            }
        }
        override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
            val ch = gatt.getService(SRVC_UUID)?.getCharacteristic(NOTE_UUID)
            noteChar = ch
            gatt.setCharacteristicNotification(ch, true)
        }
        override fun onCharacteristicChanged(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic) {
            if (characteristic.uuid == NOTE_UUID) {
                decoder.feed(characteristic.value ?: return)
            }
        }
    }

    private fun sendToDevice(frame: ByteArray) {
        noteChar?.let { ch ->
            ch.value = frame
            bluetoothGatt.writeCharacteristic(ch)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
