package com.grin.iotinspector;

import android.nfc.NdefMessage;
import android.nfc.NdefRecord;
import android.nfc.Tag;
import android.nfc.tech.MifareUltralight;
import android.nfc.tech.Ndef;
import android.nfc.tech.NfcA;
import android.nfc.tech.NfcV;

import java.io.IOException;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Locale;

final class NfcInspector {
    private static final byte ISO15693_FLAG_HIGH_DATA_RATE = 0x02;
    private static final int MAX_DIAGNOSTIC_BLOCKS = 128;

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
        inspectNfcV(tag, out);
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

    private static void inspectNfcV(Tag tag, StringBuilder out) {
        NfcV nfcV = NfcV.get(tag);
        if (nfcV == null) return;

        out.append("\n=== NFC-V / ISO15693 READ-ONLY PROBE ===\n");
        out.append(String.format(Locale.US, "Discovery response flags: 0x%02X%n", nfcV.getResponseFlags() & 0xFF));
        out.append(String.format(Locale.US, "Discovery DSFID: 0x%02X%n", nfcV.getDsfId() & 0xFF));
        out.append("Max transceive: ").append(nfcV.getMaxTransceiveLength()).append(" bytes\n");
        out.append("Política: somente comandos de leitura; WRITE/LOCK/PASSWORD desabilitados.\n");

        try {
            nfcV.connect();

            byte[] systemResponse = transceive(nfcV, "Get System Information (0x2B)",
                    new byte[]{ISO15693_FLAG_HIGH_DATA_RATE, 0x2B}, out);
            SystemInfo info = parseSystemInfo(systemResponse, out);

            int blockLimit = info != null && info.blockCount > 0
                    ? Math.min(info.blockCount, MAX_DIAGNOSTIC_BLOCKS)
                    : 32;

            if (info != null && info.blockCount > MAX_DIAGNOSTIC_BLOCKS) {
                out.append("Memória possui ").append(info.blockCount)
                        .append(" blocks; diagnóstico limitado aos primeiros ")
                        .append(MAX_DIAGNOSTIC_BLOCKS).append(".\n");
            }

            int multipleCount = Math.min(blockLimit, 4);
            if (multipleCount > 0) {
                transceive(nfcV, "Read Multiple Blocks 0.." + (multipleCount - 1) + " (0x23)",
                        new byte[]{ISO15693_FLAG_HIGH_DATA_RATE, 0x23, 0x00,
                                (byte) (multipleCount - 1)}, out);
            }

            out.append("\n--- Read Single Block (0x20) ---\n");
            int consecutiveFailures = 0;
            for (int block = 0; block < blockLimit; block++) {
                byte[] response = transceive(nfcV,
                        String.format(Locale.US, "Read block %d", block),
                        new byte[]{ISO15693_FLAG_HIGH_DATA_RATE, 0x20, (byte) block}, out);
                if (isSuccess(response)) {
                    consecutiveFailures = 0;
                    if (response.length > 1) {
                        byte[] data = Arrays.copyOfRange(response, 1, response.length);
                        out.append(String.format(Locale.US, "  BLOCK %03d DATA: %s | %s%n",
                                block, Hex.bytes(data), Hex.ascii(data)));
                    }
                } else {
                    consecutiveFailures++;
                    if (info == null && consecutiveFailures >= 4) {
                        out.append("Parando probe sem System Info após 4 blocks consecutivos não acessíveis.\n");
                        break;
                    }
                }
            }

            if (blockLimit > 0) {
                out.append("\n--- Get Multiple Block Security Status (0x2C) ---\n");
                for (int first = 0; first < blockLimit; first += 16) {
                    int count = Math.min(16, blockLimit - first);
                    transceive(nfcV,
                            String.format(Locale.US, "Security blocks %d..%d", first, first + count - 1),
                            new byte[]{ISO15693_FLAG_HIGH_DATA_RATE, 0x2C,
                                    (byte) first, (byte) (count - 1)}, out);
                }
            }
        } catch (Exception e) {
            out.append("NFC-V erro geral: ").append(e.getClass().getSimpleName()).append(": ")
                    .append(e.getMessage()).append('\n');
        } finally {
            try { nfcV.close(); } catch (Exception ignored) {}
        }
        out.append("=== FIM NFC-V PROBE ===\n");
    }

    private static byte[] transceive(NfcV nfcV, String label, byte[] command, StringBuilder out) {
        out.append("TX ").append(label).append(": ").append(Hex.bytes(command)).append('\n');
        try {
            byte[] response = nfcV.transceive(command);
            out.append("RX ").append(label).append(": ").append(Hex.bytes(response));
            if (isError(response)) {
                out.append("  [ISO15693 ERROR");
                if (response.length > 1) {
                    out.append(String.format(Locale.US, " 0x%02X", response[1] & 0xFF));
                }
                out.append(']');
            }
            out.append('\n');
            return response;
        } catch (Exception e) {
            out.append("RX ").append(label).append(": <")
                    .append(e.getClass().getSimpleName()).append(": ")
                    .append(e.getMessage()).append(">\n");
            return null;
        }
    }

    private static boolean isSuccess(byte[] response) {
        return response != null && response.length > 0 && (response[0] & 0x01) == 0;
    }

    private static boolean isError(byte[] response) {
        return response != null && response.length > 0 && (response[0] & 0x01) != 0;
    }

    private static SystemInfo parseSystemInfo(byte[] response, StringBuilder out) {
        if (!isSuccess(response) || response.length < 10) {
            out.append("System Information: indisponível ou resposta curta.\n");
            return null;
        }

        int infoFlags = response[1] & 0xFF;
        int p = 2;
        byte[] uid = Arrays.copyOfRange(response, p, p + 8);
        p += 8;

        out.append(String.format(Locale.US, "System info flags: 0x%02X%n", infoFlags));
        out.append("System UID (raw response order): ").append(Hex.bytes(uid)).append('\n');

        Integer dsfid = null;
        Integer afi = null;
        Integer blockCount = null;
        Integer blockSize = null;
        Integer icReference = null;

        if ((infoFlags & 0x01) != 0 && p < response.length) dsfid = response[p++] & 0xFF;
        if ((infoFlags & 0x02) != 0 && p < response.length) afi = response[p++] & 0xFF;
        if ((infoFlags & 0x04) != 0 && p + 1 < response.length) {
            blockCount = (response[p++] & 0xFF) + 1;
            blockSize = (response[p++] & 0x1F) + 1;
        }
        if ((infoFlags & 0x08) != 0 && p < response.length) icReference = response[p] & 0xFF;

        if (dsfid != null) out.append(String.format(Locale.US, "System DSFID: 0x%02X%n", dsfid));
        if (afi != null) out.append(String.format(Locale.US, "System AFI: 0x%02X%n", afi));
        if (blockCount != null && blockSize != null) {
            out.append("Memory: ").append(blockCount).append(" blocks x ")
                    .append(blockSize).append(" bytes = ")
                    .append(blockCount * blockSize).append(" bytes\n");
        }
        if (icReference != null) {
            out.append(String.format(Locale.US, "IC reference: 0x%02X%n", icReference));
        }

        return new SystemInfo(blockCount == null ? -1 : blockCount,
                blockSize == null ? -1 : blockSize);
    }

    private static final class SystemInfo {
        final int blockCount;
        final int blockSize;

        SystemInfo(int blockCount, int blockSize) {
            this.blockCount = blockCount;
            this.blockSize = blockSize;
        }
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
