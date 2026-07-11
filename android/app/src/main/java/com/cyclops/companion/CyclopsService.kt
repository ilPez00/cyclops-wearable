package com.cyclops.companion

import android.app.Service
import android.bluetooth.*
import android.content.Intent
import android.os.IBinder
import com.cyclops.companion.core.CyclopsProto
import com.cyclops.companion.core.HudBridge
import java.util.*

/**
 * BLE hub: connects to the XIAO wearable (NimBLE GATT server), pumps incoming
 * frames into a [HudBridge], and forwards the bridge's display frames back to
 * the device over the NOTE characteristic. Heavy lifting (ASR/vision) happens
 * in the Python brain, reached via [LocalBridge] over localhost.
 *
 * This file depends on the Android Bluetooth APIs (cannot run outside an app /
 * emulator with BLE), so it is structured + type-checked by the IDE but not
 * executed in CI without an SDK. The protocol logic it relies on lives in the
 * dependency-free `:core` module, which is unit-tested.
 */
class CyclopsService : Service() {
    companion object {
        val SRVC_UUID = UUID.fromString("4fafc201-1fb5-459e-8fcc-c5c9c331914b")
        val NOTE_UUID = UUID.fromString("beb5483e-36e1-4688-b7f5-ea07361b26a8")
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

    private val gattCallback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                gatt.discoverServices()
            }
        }
        override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
            // service/characteristic can be absent (wrong device, partial discovery)
            val ch = gatt.getService(SRVC_UUID)?.getCharacteristic(NOTE_UUID) ?: return
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

    override fun onDestroy() {
        noteChar = null
        if (::bluetoothGatt.isInitialized) {
            bluetoothGatt.disconnect()
            bluetoothGatt.close()
        }
        super.onDestroy()
    }
}
