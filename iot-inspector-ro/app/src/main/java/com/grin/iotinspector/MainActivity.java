package com.grin.iotinspector;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Typeface;
import android.nfc.NfcAdapter;
import android.nfc.Tag;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.text.method.ScrollingMovementMethod;
import android.view.Gravity;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;

public final class MainActivity extends Activity implements BleInspector.Listener {
    private static final int REQ_PERMISSIONS = 1001;
    private final StringBuilder log = new StringBuilder();
    private final List<BleInspector.DeviceRow> rows = new ArrayList<>();

    private TextView statusText;
    private TextView logText;
    private Button scanButton;
    private Button connectButton;
    private ArrayAdapter<BleInspector.DeviceRow> adapter;
    private BleInspector ble;
    private NfcAdapter nfcAdapter;
    private BleInspector.DeviceRow selected;
    private DiscordWebhookLogger webhookLogger;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(buildUi());

        ble = new BleInspector(this, this);
        nfcAdapter = NfcAdapter.getDefaultAdapter(this);
        webhookLogger = new DiscordWebhookLogger(WebhookConfig.load(this));
        webhookLogger.enqueueSessionHeader();
        append("IoT Inspector RO 1.4\n");
        append("Modo: ST25DV/NFC-V + BLE/GATT somente leitura; sem WRITE/LOCK/PASSWORD e sem comandos de atuador.\n");
        append("NFC presente: " + (nfcAdapter != null) + "\n");
        append("BLE presente: " + ble.isAvailable() + "\n");
        append("Webhook Discord: " + (webhookLogger.isConfigured() ? "configurado" : "não configurado") + "\n\n");
        requestNeededPermissions();
        refreshStatus();
    }

    private View buildUi() {
        int pad = dp(12);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad, pad, pad);

        TextView title = new TextView(this);
        title.setText("IoT Inspector RO 1.4");
        title.setTextSize(24);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        root.addView(title, new LinearLayout.LayoutParams(-1, -2));

        TextView subtitle = new TextView(this);
        subtitle.setText("ST25DV/NFC-V + BLE/GATT somente leitura");
        subtitle.setTextSize(14);
        root.addView(subtitle, new LinearLayout.LayoutParams(-1, -2));

        statusText = new TextView(this);
        statusText.setPadding(0, dp(8), 0, dp(8));
        root.addView(statusText, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.setGravity(Gravity.CENTER_VERTICAL);

        scanButton = button("Escanear BLE");
        scanButton.setOnClickListener(v -> {
            if (!hasNeededPermissions()) {
                requestNeededPermissions();
                return;
            }
            ble.startScan();
        });
        actions.addView(scanButton, new LinearLayout.LayoutParams(0, -2, 1));

        connectButton = button("Ler GATT");
        connectButton.setEnabled(false);
        connectButton.setOnClickListener(v -> {
            if (selected == null) {
                toast("Selecione um dispositivo BLE.");
                return;
            }
            ble.connectReadOnly(selected);
        });
        actions.addView(connectButton, new LinearLayout.LayoutParams(0, -2, 1));

        root.addView(actions, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout actions2 = new LinearLayout(this);
        actions2.setOrientation(LinearLayout.HORIZONTAL);
        Button settings = button("Bluetooth");
        settings.setOnClickListener(v -> startActivity(new Intent(Settings.ACTION_BLUETOOTH_SETTINGS)));
        actions2.addView(settings, new LinearLayout.LayoutParams(0, -2, 1));

        Button export = button("Compartilhar log");
        export.setOnClickListener(v -> shareLog());
        actions2.addView(export, new LinearLayout.LayoutParams(0, -2, 1));

        Button clear = button("Limpar");
        clear.setOnClickListener(v -> {
            log.setLength(0);
            logText.setText("");
        });
        actions2.addView(clear, new LinearLayout.LayoutParams(0, -2, 1));
        root.addView(actions2, new LinearLayout.LayoutParams(-1, -2));

        TextView hint = new TextView(this);
        hint.setText("NFC: aproxime e mantenha encostado. A leitura ST25DV inicia e um scan BLE paralelo também é disparado. BLE/GATT permanece somente leitura.");
        hint.setPadding(0, dp(8), 0, dp(4));
        root.addView(hint, new LinearLayout.LayoutParams(-1, -2));

        adapter = new ArrayAdapter<>(this, android.R.layout.simple_list_item_activated_1, rows);
        ListView list = new ListView(this);
        list.setChoiceMode(ListView.CHOICE_MODE_SINGLE);
        list.setAdapter(adapter);
        list.setOnItemClickListener((parent, view, position, id) -> {
            selected = rows.get(position);
            connectButton.setEnabled(true);
            append("Selecionado: " + selected.name + " [" + selected.address + "]\n");
        });
        root.addView(list, new LinearLayout.LayoutParams(-1, dp(190)));

        logText = new TextView(this);
        logText.setTextSize(12);
        logText.setTypeface(Typeface.MONOSPACE);
        logText.setTextIsSelectable(true);
        logText.setMovementMethod(new ScrollingMovementMethod());
        logText.setPadding(0, dp(8), 0, dp(16));

        ScrollView scroll = new ScrollView(this);
        scroll.addView(logText, new ScrollView.LayoutParams(-1, -2));
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        return root;
    }

    private Button button(String text) {
        Button b = new Button(this);
        b.setText(text);
        b.setAllCaps(false);
        return b;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private void refreshStatus() {
        boolean nfc = nfcAdapter != null && nfcAdapter.isEnabled();
        boolean bt = ble != null && ble.isEnabled();
        statusText.setText("NFC: " + (nfc ? "ligado" : "desligado/indisponível") +
                "   |   Bluetooth: " + (bt ? "ligado" : "desligado/indisponível"));
    }

    private boolean hasNeededPermissions() {
        if (Build.VERSION.SDK_INT >= 31) {
            return checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN) == PackageManager.PERMISSION_GRANTED &&
                    checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED;
        }
        return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    private void requestNeededPermissions() {
        if (hasNeededPermissions()) return;
        if (Build.VERSION.SDK_INT >= 31) {
            requestPermissions(new String[]{Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT}, REQ_PERMISSIONS);
        } else {
            requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION}, REQ_PERMISSIONS);
        }
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_PERMISSIONS) {
            append("Permissões BLE: " + (hasNeededPermissions() ? "OK" : "negadas/incompletas") + "\n");
        }
    }

    @Override protected void onResume() {
        super.onResume();
        refreshStatus();
        if (nfcAdapter != null) {
            int flags = NfcAdapter.FLAG_READER_NFC_A |
                    NfcAdapter.FLAG_READER_NFC_B |
                    NfcAdapter.FLAG_READER_NFC_F |
                    NfcAdapter.FLAG_READER_NFC_V |
                    NfcAdapter.FLAG_READER_NFC_BARCODE;
            nfcAdapter.enableReaderMode(this, this::onTag, flags, null);
        }
    }

    @Override protected void onPause() {
        if (nfcAdapter != null) nfcAdapter.disableReaderMode(this);
        super.onPause();
    }

    @Override protected void onDestroy() {
        if (ble != null) {
            ble.stopScan();
            ble.closeGatt();
        }
        if (webhookLogger != null) webhookLogger.close();
        super.onDestroy();
    }

    private void onTag(Tag tag) {
        if (hasNeededPermissions() && ble != null && ble.isAvailable() && ble.isEnabled()) {
            append("NFC detectado: iniciando BLE scan paralelo para correlação temporal.\n");
            try { ble.startScan(); } catch (Exception e) { append("BLE paralelo falhou: " + e.getMessage() + "\n"); }
        }

        String result;
        try {
            result = NfcInspector.inspect(tag);
        } catch (Exception e) {
            result = "NFC erro: " + e.getClass().getSimpleName() + ": " + e.getMessage() + "\n";
        }
        final String text = result;
        runOnUiThread(() -> append("\n" + text));
    }

    private void shareLog() {
        Intent send = new Intent(Intent.ACTION_SEND);
        send.setType("text/plain");
        send.putExtra(Intent.EXTRA_SUBJECT, "IoT Inspector RO log");
        send.putExtra(Intent.EXTRA_TEXT, log.toString());
        startActivity(Intent.createChooser(send, "Compartilhar log"));
    }

    private void append(String text) {
        String stamp = new SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(new Date());
        String value = "[" + stamp + "] " + text;
        log.append(value);
        if (webhookLogger != null) webhookLogger.enqueue(value);
        runOnUiThread(() -> {
            logText.append(value);
            int parentHeight = ((View) logText.getParent()).getHeight();
            if (parentHeight > 0) logText.scrollTo(0, Math.max(0, logText.getBottom() - parentHeight));
        });
    }

    private void toast(String s) { Toast.makeText(this, s, Toast.LENGTH_SHORT).show(); }

    @Override public void onLog(String text) { append(text); }

    @Override public void onDevicesChanged(List<BleInspector.DeviceRow> newRows) {
        runOnUiThread(() -> {
            rows.clear();
            rows.addAll(newRows);
            adapter.notifyDataSetChanged();
        });
    }

    @Override public void onScanState(boolean scanning) {
        runOnUiThread(() -> scanButton.setText(scanning ? "Escaneando…" : "Escanear BLE"));
    }
}
