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
        inspectNfcV(tag, out);

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
            if (record.toUri() != null) {
                out.append("    URI: ").append(record.toUri()).append('\n');
                String uri = record.toUri().toString();
                if (uri.startsWith("tel:") && uri.length() > 4) {
                    out.append("    Serial candidato: ").append(uri.substring(4)).append('\n');
                }
            }
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

    private static void inspectNfcV(Tag tag, StringBuilder out) {
        NfcV nfcV = NfcV.get(tag);
        if (nfcV == null) return;

        out.append("\n=== NFC-V / ISO15693 + ST25DV READ-ONLY ===\n");
        out.append(String.format(Locale.US, "Discovery response flags: 0x%02X%n", nfcV.getResponseFlags() & 0xFF));
        out.append(String.format(Locale.US, "Discovery DSFID: 0x%02X%n", nfcV.getDsfId() & 0xFF));
        out.append("Max transceive: ").append(nfcV.getMaxTransceiveLength()).append(" bytes\n");
        out.append("Política: READ-ONLY; sem WRITE/LOCK/PASSWORD/atuadores.\n");

        try {
            nfcV.connect();
            byte[] sys = tx(nfcV, out, "Get System Information (0x2B)", new byte[]{0x02, 0x2B});
            int blocks = parseSystemInfo(sys, out);

            // ST25DV custom read-only commands. Manufacturer code = 0x02 (ST).
            out.append("\n--- ST25DV Dynamic Registers (read-only) ---\n");
            byte[] gpo = tx(nfcV, out, "Read Dynamic GPO_CTRL_Dyn @0x00", new byte[]{0x02, (byte)0xAD, 0x02, 0x00});
            decodeDynamicByte("GPO_CTRL_Dyn", gpo, out);

            byte[] eh = tx(nfcV, out, "Read Dynamic EH_CTRL_Dyn @0x02", new byte[]{0x02, (byte)0xAD, 0x02, 0x02});
            decodeDynamicByte("EH_CTRL_Dyn", eh, out);

            byte[] mb = tx(nfcV, out, "Read Dynamic MB_CTRL_Dyn @0x0D", new byte[]{0x02, (byte)0xAD, 0x02, 0x0D});
            int mbCtrl = decodeMbCtrl(mb, out);

            byte[] ml = tx(nfcV, out, "Read Message Length (0xAB)", new byte[]{0x02, (byte)0xAB, 0x02});
            int messageBytes = decodeMessageLength(ml, out);

            if ((mbCtrl & 0x02) != 0 && messageBytes > 0) {
                out.append("HOST_PUT_MSG=1: existe mensagem do MCU/I2C na mailbox.\n");
                // Reading the final byte clears HOST_PUT_MSG by design. Preserve state by peeking all but the last byte.
                if (messageBytes == 1) {
                    out.append("Mailbox tem 1 byte; não lendo para não consumir/limpar HOST_PUT_MSG.\n");
                } else {
                    int peekBytes = Math.min(messageBytes - 1, 255);
                    byte[] req = new byte[]{0x02, (byte)0xAC, 0x02, 0x00, (byte)(peekBytes - 1)};
                    byte[] msg = tx(nfcV, out, "Read Message PEEK (sem último byte)", req);
                    decodeMailboxPeek(msg, peekBytes, out);
                    out.append("Último byte da mailbox NÃO foi lido para preservar HOST_PUT_MSG.\n");
                }
            } else if ((mbCtrl & 0x02) == 0) {
                out.append("HOST_PUT_MSG=0: nenhuma mensagem do host/MCU disponível agora.\n");
            }

            out.append("\n--- Mapa de memória pública ISO15693 ---\n");
            int limit = blocks > 0 ? blocks : 128;
            int consecutiveFailures = 0;
            for (int block = 0; block < limit; block++) {
                byte[] resp = tx(nfcV, out, "Read block " + block, new byte[]{0x02, 0x20, (byte)block});
                if (isSuccess(resp) && resp.length >= 5) {
                    consecutiveFailures = 0;
                    byte[] data = Arrays.copyOfRange(resp, 1, resp.length);
                    out.append(String.format(Locale.US, "  BLOCK %03d DATA: %s | %s%n",
                            block, Hex.bytes(data), Hex.ascii(data)));
                } else {
                    consecutiveFailures++;
                    if (isIsoError(resp)) {
                        out.append("  ").append(decodeIsoError(resp[1] & 0xFF)).append('\n');
                    }
                    if (consecutiveFailures >= 4) {
                        out.append("Parando mapa após 4 blocos consecutivos indisponíveis/perdidos.\n");
                        break;
                    }
                }
            }

            if (blocks > 0) {
                out.append("\n--- Security Status por área ---\n");
                for (int start = 0; start < blocks; start += 16) {
                    int count = Math.min(16, blocks - start);
                    byte[] resp = tx(nfcV, out, "Security blocks " + start + ".." + (start + count - 1),
                            new byte[]{0x02, 0x2C, (byte)start, (byte)(count - 1)});
                    if (isSuccess(resp)) {
                        out.append("  Security raw: ").append(Hex.bytes(Arrays.copyOfRange(resp, 1, resp.length))).append('\n');
                    }
                }
            }
        } catch (Exception e) {
            out.append("NFC-V erro: ").append(e.getClass().getSimpleName()).append(": ")
                    .append(e.getMessage()).append('\n');
        } finally {
            try { nfcV.close(); } catch (Exception ignored) {}
        }

        out.append("=== FIM NFC-V/ST25DV ===\n");
    }

    private static byte[] tx(NfcV nfcV, StringBuilder out, String label, byte[] req) {
        out.append("TX ").append(label).append(": ").append(Hex.bytes(req)).append('\n');
        try {
            byte[] resp = nfcV.transceive(req);
            out.append("RX ").append(label).append(": ").append(Hex.bytes(resp));
            if (isIsoError(resp)) out.append("  [").append(decodeIsoError(resp[1] & 0xFF)).append(']');
            out.append('\n');
            return resp;
        } catch (Exception e) {
            out.append("RX ").append(label).append(": <").append(e.getClass().getSimpleName())
                    .append(": ").append(e.getMessage()).append(">\n");
            return null;
        }
    }

    private static int parseSystemInfo(byte[] r, StringBuilder out) {
        if (!isSuccess(r) || r.length < 2) {
            out.append("System Information: indisponível ou resposta curta.\n");
            return -1;
        }
        int infoFlags = r[1] & 0xFF;
        out.append(String.format(Locale.US, "System info flags: 0x%02X%n", infoFlags));
        int i = 2;
        if (r.length >= i + 8) {
            out.append("System UID (raw response order): ")
                    .append(Hex.bytes(Arrays.copyOfRange(r, i, i + 8))).append('\n');
            i += 8;
        }
        if ((infoFlags & 0x01) != 0 && i < r.length) out.append(String.format(Locale.US, "System DSFID: 0x%02X%n", r[i++] & 0xFF));
        if ((infoFlags & 0x02) != 0 && i < r.length) out.append(String.format(Locale.US, "System AFI: 0x%02X%n", r[i++] & 0xFF));
        int blocks = -1;
        if ((infoFlags & 0x04) != 0 && i + 1 < r.length) {
            blocks = (r[i++] & 0xFF) + 1;
            int blockSize = (r[i++] & 0x1F) + 1;
            out.append("Memory: ").append(blocks).append(" blocks x ").append(blockSize)
                    .append(" bytes = ").append(blocks * blockSize).append(" bytes\n");
        }
        if ((infoFlags & 0x08) != 0 && i < r.length) {
            int ic = r[i] & 0xFF;
            out.append(String.format(Locale.US, "IC reference: 0x%02X%n", ic));
            if (ic == 0x24) out.append("Chip candidate: STMicroelectronics ST25DV04K family (IC ref 0x24).\n");
        }
        return blocks;
    }

    private static void decodeDynamicByte(String name, byte[] r, StringBuilder out) {
        if (isSuccess(r) && r.length >= 2) {
            out.append(String.format(Locale.US, "%s = 0x%02X%n", name, r[1] & 0xFF));
        }
    }

    private static int decodeMbCtrl(byte[] r, StringBuilder out) {
        if (!isSuccess(r) || r.length < 2) {
            out.append("MB_CTRL_Dyn: indisponível.\n");
            return 0;
        }
        int v = r[1] & 0xFF;
        out.append(String.format(Locale.US, "MB_CTRL_Dyn = 0x%02X%n", v));
        out.append("  MB_EN=" + bit(v,0) + " HOST_PUT_MSG=" + bit(v,1) + " RF_PUT_MSG=" + bit(v,2) + '\n');
        out.append("  HOST_MISS_MSG=" + bit(v,4) + " RF_MISS_MSG=" + bit(v,5) + '\n');
        out.append("  HOST_CURRENT_MSG=" + bit(v,6) + " RF_CURRENT_MSG=" + bit(v,7) + '\n');
        return v;
    }

    private static int decodeMessageLength(byte[] r, StringBuilder out) {
        if (!isSuccess(r) || r.length < 2) {
            out.append("MB_LEN_Dyn: indisponível.\n");
            return 0;
        }
        int raw = r[1] & 0xFF;
        int bytes = raw + 1;
        out.append(String.format(Locale.US, "MB_LEN_Dyn raw=0x%02X => %d byte(s) quando há mensagem.%n", raw, bytes));
        return bytes;
    }

    private static void decodeMailboxPeek(byte[] r, int expected, StringBuilder out) {
        if (!isSuccess(r) || r.length < 2) return;
        byte[] data = Arrays.copyOfRange(r, 1, r.length);
        out.append("Mailbox PEEK bytes recebidos: ").append(data.length).append('/').append(expected).append('\n');
        out.append("  HEX: ").append(Hex.bytes(data)).append('\n');
        out.append("  ASCII: ").append(Hex.ascii(data)).append('\n');
    }

    private static int bit(int v, int b) { return (v >> b) & 1; }
    private static boolean isSuccess(byte[] r) { return r != null && r.length >= 1 && (r[0] & 0x01) == 0; }
    private static boolean isIsoError(byte[] r) { return r != null && r.length >= 2 && (r[0] & 0x01) != 0; }

    private static String decodeIsoError(int code) {
        switch (code) {
            case 0x01: return "ISO15693 ERROR 0x01: command not supported";
            case 0x02: return "ISO15693 ERROR 0x02: command not recognized";
            case 0x03: return "ISO15693 ERROR 0x03: option not supported";
            case 0x0F: return "ISO15693 ERROR 0x0F: error, no information";
            case 0x10: return "ISO15693 ERROR 0x10: block not available";
            case 0x11: return "ISO15693 ERROR 0x11: block already locked";
            case 0x12: return "ISO15693 ERROR 0x12: block locked";
            case 0x13: return "ISO15693 ERROR 0x13: programming failed";
            case 0x14: return "ISO15693 ERROR 0x14: lock failed";
            case 0x15: return "ISO15693 ERROR 0x15: protected/secured area";
            default: return String.format(Locale.US, "ISO15693 ERROR 0x%02X", code);
        }
    }
}
