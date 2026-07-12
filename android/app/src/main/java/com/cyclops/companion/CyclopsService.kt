package com.cyclops.companion

import android.app.Service
import android.bluetooth.*
import android.content.Context
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
        val CCCD_UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")
        const val EXTRA_MAC = "com.cyclops.companion.extra.MAC"
        const val RECONNECT_MIN_MS = 1_000L
        const val RECONNECT_MAX_MS = 60_000L
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
                reconnectDelayMs = RECONNECT_MIN_MS  // link is up: reset backoff
                gatt.discoverServices()
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                // a dropped wearable link must heal itself — this service IS
                // the phone side of the product; a one-shot connect was dead
                // on the first walk out of range
                noteChar = null
                scheduleReconnect()
            }
        }
        override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
            // service/characteristic can be absent (wrong device, partial discovery)
            val ch = gatt.getService(SRVC_UUID)?.getCharacteristic(NOTE_UUID) ?: return
            noteChar = ch
            // Local flag AND the CCCD (0x2902) write — without the descriptor
            // the wearable never notifies (same bug class as RingActivity).
            gatt.setCharacteristicNotification(ch, true)
            ch.getDescriptor(CCCD_UUID)?.let { d ->
                d.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                gatt.writeDescriptor(d)
            }
        }
        override fun onCharacteristicWrite(
            gatt: BluetoothGatt, ch: BluetoothGattCharacteristic, status: Int
        ) {
            drainTx()  // one in-flight GATT write at a time
        }
        override fun onCharacteristicChanged(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic) {
            if (characteristic.uuid == NOTE_UUID) {
                decoder.feed(characteristic.value ?: return)
            }
        }
    }

    private var adapter: BluetoothAdapter? = null
    private var mac: String? = null
    private val handler = android.os.Handler(android.os.Looper.getMainLooper())
    private var reconnectDelayMs = RECONNECT_MIN_MS

    private fun scheduleReconnect() {
        val target = mac ?: return
        val delay = reconnectDelayMs
        reconnectDelayMs = (reconnectDelayMs * 2).coerceAtMost(RECONNECT_MAX_MS)
        handler.postDelayed({ connect(target) }, delay)
    }

    /** Initiate a GATT connection to the wearable at [mac].
     * The caller must already hold BLUETOOTH_CONNECT (API 31+);
     * the activity requests it before starting this service. */
    fun connect(mac: String) {
        this.mac = mac
        val mgr = getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager ?: return
        adapter = mgr.adapter
        val device = adapter?.getRemoteDevice(mac) ?: return
        if (::bluetoothGatt.isInitialized) bluetoothGatt.close()
        bluetoothGatt = device.connectGatt(this, false, gattCallback)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        intent?.getStringExtra(EXTRA_MAC)?.let { connect(it) }
        return START_STICKY
    }

    // Android GATT drops writes issued while one is in flight; queue + drain.
    private val txQueue = ArrayDeque<ByteArray>()

    private fun sendToDevice(frame: ByteArray) {
        synchronized(txQueue) { txQueue.add(frame) }
        drainTx()
    }

    private fun drainTx() {
        val ch = noteChar ?: return
        val frame = synchronized(txQueue) { txQueue.removeFirstOrNull() } ?: return
        ch.value = frame
        if (!bluetoothGatt.writeCharacteristic(ch)) {
            // write refused (busy/link down): requeue at the front, the next
            // onCharacteristicWrite or reconnect will drain it
            synchronized(txQueue) { txQueue.addFirst(frame) }
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)  // stop any pending reconnect
        mac = null
        noteChar = null
        if (::bluetoothGatt.isInitialized) {
            bluetoothGatt.disconnect()
            bluetoothGatt.close()
        }
        super.onDestroy()
    }
}
