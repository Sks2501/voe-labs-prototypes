package com.grin.iotinspector;

import java.nio.charset.StandardCharsets;
import java.util.Locale;

final class Hex {
    private Hex() {}

    static String bytes(byte[] data) {
        if (data == null) return "<null>";
        StringBuilder sb = new StringBuilder(data.length * 3);
        for (int i = 0; i < data.length; i++) {
            if (i > 0) sb.append(' ');
            sb.append(String.format(Locale.US, "%02X", data[i] & 0xFF));
        }
        return sb.toString();
    }

    static String compact(byte[] data) {
        if (data == null) return "";
        StringBuilder sb = new StringBuilder(data.length * 2);
        for (byte b : data) sb.append(String.format(Locale.US, "%02X", b & 0xFF));
        return sb.toString();
    }

    static String ascii(byte[] data) {
        if (data == null) return "";
        String raw = new String(data, StandardCharsets.UTF_8);
        StringBuilder sb = new StringBuilder(raw.length());
        for (int i = 0; i < raw.length(); i++) {
            char c = raw.charAt(i);
            sb.append(c >= 32 && c <= 126 ? c : '.');
        }
        return sb.toString();
    }
}
