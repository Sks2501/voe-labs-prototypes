package com.grin.iotinspector;

import android.nfc.NdefMessage;
import android.nfc.NdefRecord;
import android.nfc.Tag;
import android.nfc.tech.MifareUltralight;
import android.nfc.tech.Ndef;
import android.nfc.tech.NfcA;

import java.io.IOException;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Locale;

final class NfcInspector {
    private NfcInspector() {}

    static String inspect(Tag tag) {
        StringBuilder out = new StringBuilder();
        out.append("=== NFC TAG ===\n");
        out.append("UID: ").append(Hex.bytes(tag.getId())).append('\n');
        out.append("UID compact: ").append(Hex.compact(tag.getId())).append('\n');
        out.append("Tecnologias:\n");
        for (String tech : tag.getTechList()) out.append("  - ").append(tech).append('\n');

        inspectNfcA(tag, out);
        inspectNdef(tag, out);
        inspectUltralight(tag, out);

        out.append("=== FIM NFC ===\n");
        return out.toString();
    }

    private static void inspectNfcA(Tag tag, StringBuilder out) {
        NfcA nfcA = NfcA.get(tag);
        if (nfcA == null) return;
        out.append("NFC-A ATQA: ").append(Hex.bytes(nfcA.getAtqa())).append('\n');
        out.append(String.format(Locale.US, "NFC-A SAK: 0x%02X%n", nfcA.getSak() & 0xFF));
        out.append("NFC-A max transceive: ").append(nfcA.getMaxTransceiveLength()).append(" bytes\n");
    }

    private static void inspectNdef(Tag tag, StringBuilder out) {
        Ndef ndef = Ndef.get(tag);
        if (ndef == null) {
            out.append("NDEF: não disponível\n");
            return;
        }
        try {
            ndef.connect();
            out.append("NDEF type: ").append(ndef.getType()).append('\n');
            out.append("NDEF max size: ").append(ndef.getMaxSize()).append(" bytes\n");
            out.append("NDEF writable: ").append(ndef.isWritable()).append('\n');
            out.append("NDEF canMakeReadOnly: ").append(ndef.canMakeReadOnly()).append('\n');
            NdefMessage message = ndef.getNdefMessage();
            if (message == null) {
                out.append("NDEF message: vazio\n");
            } else {
                NdefRecord[] records = message.getRecords();
                out.append("NDEF records: ").append(records.length).append('\n');
                for (int i = 0; i < records.length; i++) inspectRecord(records[i], i, out);
            }
        } catch (Exception e) {
            out.append("NDEF erro: ").append(e.getClass().getSimpleName()).append(": ")
                    .append(e.getMessage()).append('\n');
        } finally {
            try { ndef.close(); } catch (Exception ignored) {}
        }
    }

    private static void inspectRecord(NdefRecord record, int index, StringBuilder out) {
        out.append("  Record #").append(index + 1).append('\n');
        out.append("    TNF: ").append(record.getTnf()).append('\n');
        out.append("    Type hex: ").append(Hex.bytes(record.getType())).append('\n');
        out.append("    Type ASCII: ").append(Hex.ascii(record.getType())).append('\n');
        out.append("    ID: ").append(Hex.bytes(record.getId())).append('\n');
        out.append("    Payload hex: ").append(Hex.bytes(record.getPayload())).append('\n');
        out.append("    Payload ASCII: ").append(Hex.ascii(record.getPayload())).append('\n');

        String text = decodeTextRecord(record);
        if (text != null) out.append("    Text: ").append(text).append('\n');
        try {
            if (record.toUri() != null) out.append("    URI: ").append(record.toUri()).append('\n');
        } catch (Exception ignored) {}
    }

    private static String decodeTextRecord(NdefRecord record) {
        if (record.getTnf() != NdefRecord.TNF_WELL_KNOWN ||
                !Arrays.equals(record.getType(), NdefRecord.RTD_TEXT)) return null;
        byte[] payload = record.getPayload();
        if (payload == null || payload.length < 1) return "";
        int status = payload[0] & 0xFF;
        boolean utf16 = (status & 0x80) != 0;
        int languageLength = status & 0x3F;
        int textOffset = 1 + languageLength;
        if (textOffset > payload.length) return "<registro texto inválido>";
        Charset charset = utf16 ? StandardCharsets.UTF_16 : StandardCharsets.UTF_8;
        return new String(payload, textOffset, payload.length - textOffset, charset);
    }

    private static void inspectUltralight(Tag tag, StringBuilder out) {
        MifareUltralight ultralight = MifareUltralight.get(tag);
        if (ultralight == null) return;
        out.append("MIFARE Ultralight: detectado\n");
        out.append("MIFARE type: ").append(ultralight.getType()).append('\n');
        out.append("MIFARE max transceive: ").append(ultralight.getMaxTransceiveLength()).append(" bytes\n");
        try {
            ultralight.connect();
            for (int page = 0; page < 64; page += 4) {
                try {
                    byte[] data = ultralight.readPages(page);
                    if (data == null || data.length == 0) break;
                    out.append(String.format(Locale.US, "Pages %02d-%02d: %s | %s%n",
                            page, page + 3, Hex.bytes(data), Hex.ascii(data)));
                } catch (IOException e) {
                    out.append("Leitura pública encerrou na page ").append(page)
                            .append(" (não acessível/fora da memória).\n");
                    break;
                }
            }
        } catch (Exception e) {
            out.append("MIFARE erro: ").append(e.getClass().getSimpleName()).append(": ")
                    .append(e.getMessage()).append('\n');
        } finally {
            try { ultralight.close(); } catch (Exception ignored) {}
        }
    }
}
