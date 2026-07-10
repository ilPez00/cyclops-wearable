package com.cyclops.companion

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothProfile
import android.bluetooth.le.BluetoothLeScanner
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.cyclops.companion.core.GaugeGeometry
import androidx.core.app.ActivityCompat
import com.cyclops.companion.core.RingProto
import com.cyclops.companion.core.RingSample
import com.cyclops.companion.databinding.ActivityRingBinding

/**
 * Reads live HR / SpO2 / battery from a COLMI R02 (and R06/R10) smart ring over
 * BLE. Protocol logic lives in core.RingProto (shared with firmware/Python).
 *
 * The ring speaks a Nordic UART Service (NUS) clone — no pairing, no auth.
 * SERVICE 6E40FFF0-...-E50E24DCCA9E, RX 6E400002-..., TX 6E400003-...
 * Every frame is 16 bytes; CRC = sum(byte[0..14]) & 0xFF.
 */
class RingActivity : AppCompatActivity() {

    private lateinit var binding: ActivityRingBinding

    private val bluetoothAdapter: BluetoothAdapter? by lazy {
        val bm = getSystemService(BLUETOOTH_SERVICE) as? android.bluetooth.BluetoothManager
        bm?.adapter
    }
    private var scanner: BluetoothLeScanner? = null
    private var gatt: BluetoothGatt? = null
    private var txChar: BluetoothGattCharacteristic? = null
    private var rxChar: BluetoothGattCharacteristic? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityRingBinding.inflate(layoutInflater)
        setContentView(binding.root)
        binding.btnRingConnect.setOnClickListener { toggleConnect() }
        updateStatus(getString(R.string.ring_idle))
    }

    override fun onStop() {
        super.onStop()
        disconnect()
    }

    private fun toggleConnect() {
        if (gatt != null || scanner != null) disconnect() else connect()
    }

    private fun connect() {
        val adapter = bluetoothAdapter
        if (adapter == null || !adapter.isEnabled) { updateStatus("Bluetooth off / unavailable"); return }
        if (!hasPerms()) { requestPerms(); return }
        scanner = adapter.bluetoothLeScanner
        updateStatus("Scanning for R02_ ...")
        if (ActivityCompat.checkSelfPermission(this,
                if (Build.VERSION.SDK_INT >= 31) Manifest.permission.BLUETOOTH_SCAN
                else Manifest.permission.BLUETOOTH) != PackageManager.PERMISSION_GRANTED) {
            requestPerms(); return
        }
        @Suppress("MissingPermission")
        scanner?.startScan(scanCb)
    }

    private val scanCb = object : ScanCallback() {
        @Suppress("MissingPermission")
        override fun onScanResult(callbackType: Int, result: ScanResult?) {
            val dev = result?.device ?: return
            val name = result.scanRecord?.deviceName ?: dev.name ?: ""
            if (name.startsWith("R02", ignoreCase = true) ||
                name.startsWith("R06", ignoreCase = true) ||
                name.startsWith("R10", ignoreCase = true)) {
                scanner?.stopScan(this); scanner = null
                updateStatus("Connecting to $name")
                gatt = dev.connectGatt(this@RingActivity, false, gattCb)
            }
        }
    }

    private val gattCb = object : BluetoothGattCallback() {
        @Suppress("MissingPermission")
        override fun onConnectionStateChange(g: BluetoothGatt?, status: Int, newState: Int) {
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                updateStatus("Connected — discovering services")
                g?.discoverServices()
            } else {
                runOnUiThread { updateStatus("Disconnected"); resetUi() }
                gatt = null
            }
        }

        @Suppress("MissingPermission")
        override fun onServicesDiscovered(g: BluetoothGatt?, status: Int) {
            val svc = g?.getService(RingProto.SRVC) ?: run {
                runOnUiThread { updateStatus("Ring service not found") }; return
            }
            rxChar = svc.getCharacteristic(RingProto.RX)
            txChar = svc.getCharacteristic(RingProto.TX) ?: run {
                runOnUiThread { updateStatus("TX characteristic missing") }; return
            }
            g.setCharacteristicNotification(txChar, true)
            runOnUiThread { updateStatus("Linked — requesting battery + live HR/SpO2") }
            sendPacket(RingProto.batteryPacket())
            sendPacket(RingProto.startRealTime(RingProto.RT_HEART_RATE))
            sendPacket(RingProto.startRealTime(RingProto.RT_SPO2))
        }

        @Suppress("MissingPermission")
        override fun onCharacteristicChanged(
            g: BluetoothGatt?, ch: BluetoothGattCharacteristic?
        ) {
            val data = ch?.value ?: return
            RingProto.parse(data)?.let { onSample(it) }
        }
    }

    @Suppress("MissingPermission")
    private fun sendPacket(pkt: ByteArray) {
        val rx = rxChar ?: return
        rx.value = pkt
        rx.writeType = BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
        gatt?.writeCharacteristic(rx)
    }

    private fun onSample(s: RingSample) {
        runOnUiThread {
            if (s.hr != 0) {
                binding.gaugeHr.setValue(s.hr / 200f, GaugeGeometry.healthLabel(s.hr))
            } else {
                binding.gaugeHr.label = "--"
            }
            if (s.spo2 != 0) {
                binding.gaugeSpo2.setValue(s.spo2 / 100f, GaugeGeometry.healthLabel(s.spo2, "%"))
            } else {
                binding.gaugeSpo2.label = "--"
            }
            if (s.battery != 0 || s.charging) {
                binding.barBatt.fraction = s.battery / 100f
                binding.barBatt.label = "Battery ${s.battery}%" +
                    if (s.charging) " (charging)" else ""
            }
        }
    }

    @Suppress("MissingPermission")
    private fun disconnect() {
        gatt?.let { it.disconnect(); it.close() }
        gatt = null
        scanner?.stopScan(scanCb); scanner = null
        rxChar = null; txChar = null
        runOnUiThread {
            updateStatus(getString(R.string.ring_idle))
            binding.btnRingConnect.text = getString(R.string.ring_connect)
        }
    }

    private fun resetUi() {
        binding.gaugeHr.label = "--"
        binding.gaugeSpo2.label = "--"
        binding.barBatt.fraction = 0f
        binding.barBatt.label = "Battery --%"
        binding.btnRingConnect.text = getString(R.string.ring_connect)
    }

    private fun updateStatus(s: String) {
        runOnUiThread {
            binding.txtRingStatus.text = s
            binding.btnRingConnect.text = if (gatt != null || scanner != null)
                getString(R.string.ring_disconnect) else getString(R.string.ring_connect)
        }
    }

    private fun hasPerms(): Boolean {
        val needed = if (Build.VERSION.SDK_INT >= 31)
            arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
        else
            arrayOf(Manifest.permission.BLUETOOTH, Manifest.permission.BLUETOOTH_ADMIN)
        return needed.all { ActivityCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED }
    }

    private fun requestPerms() {
        val needed = if (Build.VERSION.SDK_INT >= 31)
            arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
        else
            arrayOf(Manifest.permission.BLUETOOTH, Manifest.permission.BLUETOOTH_ADMIN)
        ActivityCompat.requestPermissions(this, needed, 1)
    }

    private fun toast(m: String) = Toast.makeText(this, m, Toast.LENGTH_LONG).show()
}
