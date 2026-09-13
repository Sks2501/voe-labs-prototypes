package com.grin.iotinspector;

import android.Manifest;
import android.annotation.SuppressLint;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattService;
import android.bluetooth.BluetoothManager;
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanRecord;
import android.bluetooth.le.ScanResult;
import android.bluetooth.le.ScanSettings;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.ParcelUuid;
import android.util.SparseArray;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Queue;

final class BleInspector {
    interface Listener {
        void onLog(String text);
        void onDevicesChanged(List<DeviceRow> rows);
        void onScanState(boolean scanning);
    }

    static final class DeviceRow {
        final BluetoothDevice device;
        final String name;
        final String address;
        int rssi;
        long lastSeenMs;

        DeviceRow(BluetoothDevice device, String name, String address, int rssi, long lastSeenMs) {
            this.device = device;
            this.name = name;
            this.address = address;
            this.rssi = rssi;
            this.lastSeenMs = lastSeenMs;
        }

        @Override public String toString() {
            return (name == null || name.isBlank() ? "<sem nome>" : name) + "\n" +
                    address + "   RSSI " + rssi + " dBm";
        }
    }

    private final Context context;
    private final Listener listener;
    private final BluetoothAdapter adapter;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Map<String, DeviceRow> devices = new LinkedHashMap<>();
    private final Queue<BluetoothGattCharacteristic> readQueue = new ArrayDeque<>();
    private BluetoothLeScanner scanner;
    private BluetoothGatt gatt;
    private boolean scanning;

    BleInspector(Context context, Listener listener) {
        this.context = context.getApplicationContext();
        this.listener = listener;
        BluetoothManager manager = (BluetoothManager) context.getSystemService(Context.BLUETOOTH_SERVICE);
        this.adapter = manager == null ? null : manager.getAdapter();
    }

    boolean isAvailable() { return adapter != null; }
    boolean isEnabled() { return adapter != null && adapter.isEnabled(); }

    @SuppressLint("MissingPermission")
    void startScan() {
        if (!hasScanPermission()) {
            listener.onLog("BLE: permissão de scan ausente.\n");
            return;
        }
        if (adapter == null || !adapter.isEnabled()) {
            listener.onLog("BLE: Bluetooth indisponível/desligado.\n");
            return;
        }
        stopScan();
        devices.clear();
        notifyDevices();
        scanner = adapter.getBluetoothLeScanner();
        if (scanner == null) {
            listener.onLog("BLE: scanner indisponível.\n");
            return;
        }
        ScanSettings settings = new ScanSettings.Builder()
                .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
                .build();
        scanner.startScan(null, settings, callback);
        scanning = true;
        listener.onScanState(true);
        listener.onLog("=== BLE SCAN INICIADO (15 s) ===\n");
        handler.postDelayed(this::stopScan, 15_000L);
    }

    @SuppressLint("MissingPermission")
    void stopScan() {
        handler.removeCallbacksAndMessages(null);
        if (scanner != null && scanning && hasScanPermission()) {
            try { scanner.stopScan(callback); } catch (Exception ignored) {}
        }
        if (scanning) listener.onLog("=== BLE SCAN ENCERRADO ===\n");
        scanning = false;
        listener.onScanState(false);
    }

    @SuppressLint("MissingPermission")
    void connectReadOnly(DeviceRow row) {
        if (!hasConnectPermission()) {
            listener.onLog("GATT: permissão de conexão ausente.\n");
            return;
        }
        closeGatt();
        listener.onLog("=== GATT READ-ONLY ===\nConectando: " + row.name + " [" + row.address + "]\n");
        gatt = row.device.connectGatt(context, false, gattCallback, BluetoothDevice.TRANSPORT_LE);
    }

    @SuppressLint("MissingPermission")
    void closeGatt() {
        readQueue.clear();
        if (gatt != null) {
            try { gatt.disconnect(); } catch (Exception ignored) {}
            try { gatt.close(); } catch (Exception ignored) {}
            gatt = null;
        }
    }

    private boolean hasScanPermission() {
        if (Build.VERSION.SDK_INT >= 31) {
            return context.checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN) == PackageManager.PERMISSION_GRANTED;
        }
        return context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    private boolean hasConnectPermission() {
        return Build.VERSION.SDK_INT < 31 ||
                context.checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED;
    }

    @SuppressLint("MissingPermission")
    private String safeName(BluetoothDevice device, ScanRecord record) {
        String n = record == null ? null : record.getDeviceName();
        if (n != null && !n.isBlank()) return n;
        if (hasConnectPermission()) {
            try { return device.getName(); } catch (Exception ignored) {}
        }
        return null;
    }

    private final ScanCallback callback = new ScanCallback() {
        @Override public void onScanResult(int callbackType, ScanResult result) { process(result); }
        @Override public void onBatchScanResults(List<ScanResult> results) {
            for (ScanResult r : results) process(r);
        }
        @Override public void onScanFailed(int errorCode) {
            listener.onLog("BLE scan falhou: código " + errorCode + "\n");
            scanning = false;
            listener.onScanState(false);
        }
    };

    @SuppressLint("MissingPermission")
    private void process(ScanResult result) {
        BluetoothDevice device = result.getDevice();
        String address = device.getAddress();
        String name = safeName(device, result.getScanRecord());
        DeviceRow row = devices.get(address);
        if (row == null) {
            row = new DeviceRow(device, name, address, result.getRssi(), System.currentTimeMillis());
            devices.put(address, row);
            listener.onLog(formatAdvertisement(result, name));
        } else {
            row.rssi = result.getRssi();
            row.lastSeenMs = System.currentTimeMillis();
        }
        notifyDevices();
    }

    private void notifyDevices() {
        List<DeviceRow> rows = new ArrayList<>(devices.values());
        rows.sort(Comparator.comparingInt((DeviceRow r) -> r.rssi).reversed());
        listener.onDevicesChanged(rows);
    }

    private String formatAdvertisement(ScanResult result, String name) {
        StringBuilder out = new StringBuilder();
        ScanRecord record = result.getScanRecord();
        out.append("\n--- BLE DEVICE ---\n");
        out.append("Nome: ").append(name == null ? "<sem nome>" : name).append('\n');
        out.append("MAC: ").append(result.getDevice().getAddress()).append('\n');
        out.append("RSSI: ").append(result.getRssi()).append(" dBm\n");
        out.append("Connectable: ");
        if (Build.VERSION.SDK_INT >= 26) out.append(result.isConnectable()); else out.append("n/a");
        out.append('\n');
        if (record == null) {
            out.append("ScanRecord: <null>\n");
            return out.toString();
        }
        out.append("TX power: ").append(record.getTxPowerLevel()).append('\n');
        out.append("Raw advertisement: ").append(Hex.bytes(record.getBytes())).append('\n');

        List<ParcelUuid> serviceUuids = record.getServiceUuids();
        if (serviceUuids != null && !serviceUuids.isEmpty()) {
            out.append("Service UUIDs:\n");
            for (ParcelUuid uuid : serviceUuids) out.append("  - ").append(uuid).append('\n');
        }

        SparseArray<byte[]> manufacturer = record.getManufacturerSpecificData();
        if (manufacturer != null && manufacturer.size() > 0) {
            out.append("Manufacturer data:\n");
            for (int i = 0; i < manufacturer.size(); i++) {
                int id = manufacturer.keyAt(i);
                byte[] data = manufacturer.valueAt(i);
                out.append(String.format(Locale.US, "  - 0x%04X: %s | %s%n", id, Hex.bytes(data), Hex.ascii(data)));
            }
        }

        Map<ParcelUuid, byte[]> serviceData = record.getServiceData();
        if (serviceData != null && !serviceData.isEmpty()) {
            out.append("Service data:\n");
            for (Map.Entry<ParcelUuid, byte[]> e : serviceData.entrySet()) {
                out.append("  - ").append(e.getKey()).append(": ")
                        .append(Hex.bytes(e.getValue())).append(" | ")
                        .append(Hex.ascii(e.getValue())).append('\n');
            }
        }
        return out.toString();
    }

    private final BluetoothGattCallback gattCallback = new BluetoothGattCallback() {
        @Override public void onConnectionStateChange(BluetoothGatt g, int status, int newState) {
            listener.onLog("GATT connection: status=" + status + " state=" + newState + "\n");
            if (status == BluetoothGatt.GATT_SUCCESS && newState == android.bluetooth.BluetoothProfile.STATE_CONNECTED) {
                if (!hasConnectPermission()) return;
                try {
                    boolean started = g.discoverServices();
                    listener.onLog("discoverServices(): " + started + "\n");
                } catch (SecurityException e) {
                    listener.onLog("GATT permissão: " + e.getMessage() + "\n");
                }
            }
        }

        @Override public void onServicesDiscovered(BluetoothGatt g, int status) {
            if (status != BluetoothGatt.GATT_SUCCESS) {
                listener.onLog("GATT service discovery falhou: " + status + "\n");
                return;
            }
            StringBuilder out = new StringBuilder("GATT serviços descobertos:\n");
            readQueue.clear();
            for (BluetoothGattService service : g.getServices()) {
                out.append("SERVICE ").append(service.getUuid()).append('\n');
                for (BluetoothGattCharacteristic c : service.getCharacteristics()) {
                    out.append("  CHAR ").append(c.getUuid())
                            .append(" props=").append(properties(c.getProperties())).append('\n');
                    if ((c.getProperties() & BluetoothGattCharacteristic.PROPERTY_READ) != 0) {
                        readQueue.add(c);
                    }
                }
            }
            listener.onLog(out.toString());
            listener.onLog("Características READ na fila: " + readQueue.size() + "\n");
            readNext(g);
        }

        @Override public void onCharacteristicRead(BluetoothGatt g, BluetoothGattCharacteristic characteristic, int status) {
            byte[] value = characteristic.getValue();
            handleRead(g, characteristic, value, status);
        }

        @Override public void onCharacteristicRead(BluetoothGatt g, BluetoothGattCharacteristic characteristic, byte[] value, int status) {
            handleRead(g, characteristic, value, status);
        }
    };

    private void handleRead(BluetoothGatt g, BluetoothGattCharacteristic c, byte[] value, int status) {
        if (status == BluetoothGatt.GATT_SUCCESS) {
            listener.onLog("READ " + c.getUuid() + " = " + Hex.bytes(value) + " | " + Hex.ascii(value) + "\n");
        } else {
            listener.onLog("READ " + c.getUuid() + " falhou status=" + status + "\n");
        }
        readNext(g);
    }

    @SuppressLint("MissingPermission")
    private void readNext(BluetoothGatt g) {
        BluetoothGattCharacteristic c = readQueue.poll();
        if (c == null) {
            listener.onLog("=== GATT READ-ONLY CONCLUÍDO ===\n");
            return;
        }
        if (!hasConnectPermission()) {
            listener.onLog("GATT: permissão perdida.\n");
            return;
        }
        try {
            boolean ok = g.readCharacteristic(c);
            if (!ok) {
                listener.onLog("READ " + c.getUuid() + " não iniciou.\n");
                handler.post(() -> readNext(g));
            }
        } catch (Exception e) {
            listener.onLog("READ " + c.getUuid() + " erro: " + e.getClass().getSimpleName() + ": " + e.getMessage() + "\n");
            handler.post(() -> readNext(g));
        }
    }

    private static String properties(int p) {
        List<String> names = new ArrayList<>();
        if ((p & BluetoothGattCharacteristic.PROPERTY_BROADCAST) != 0) names.add("BROADCAST");
        if ((p & BluetoothGattCharacteristic.PROPERTY_READ) != 0) names.add("READ");
        if ((p & BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE) != 0) names.add("WRITE_NO_RESPONSE");
        if ((p & BluetoothGattCharacteristic.PROPERTY_WRITE) != 0) names.add("WRITE");
        if ((p & BluetoothGattCharacteristic.PROPERTY_NOTIFY) != 0) names.add("NOTIFY");
        if ((p & BluetoothGattCharacteristic.PROPERTY_INDICATE) != 0) names.add("INDICATE");
        if ((p & BluetoothGattCharacteristic.PROPERTY_SIGNED_WRITE) != 0) names.add("SIGNED_WRITE");
        return names.isEmpty() ? "0x" + Integer.toHexString(p) : String.join("|", names);
    }
}
