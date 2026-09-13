package com.grin.iotinspector;

import android.os.Build;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Locale;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Envia somente o log de diagnóstico gerado pelo aplicativo para um webhook Discord.
 * Não executa comandos BLE/NFC e não altera o dispositivo inspecionado.
 */
final class DiscordWebhookLogger implements AutoCloseable {
    private static final int MAX_DISCORD_CONTENT = 1900;
    private static final int MAX_QUEUE_CHARS = 64 * 1024;
    private static final long FLUSH_DELAY_MS = 1800L;

    private final String webhookUrl;
    private final ScheduledExecutorService executor = Executors.newSingleThreadScheduledExecutor(r -> {
        Thread t = new Thread(r, "discord-webhook-logger");
        t.setDaemon(true);
        return t;
    });
    private final Object lock = new Object();
    private final StringBuilder pending = new StringBuilder();
    private final Deque<String> retryQueue = new ArrayDeque<>();
    private final AtomicBoolean flushScheduled = new AtomicBoolean(false);
    private volatile boolean closed;

    DiscordWebhookLogger(String webhookUrl) {
        this.webhookUrl = webhookUrl == null ? "" : webhookUrl.trim();
    }

    boolean isConfigured() {
        return webhookUrl.startsWith("https://discord.com/api/webhooks/") ||
                webhookUrl.startsWith("https://discordapp.com/api/webhooks/");
    }

    void enqueue(String text) {
        if (!isConfigured() || closed || text == null || text.isEmpty()) return;
        synchronized (lock) {
            if (pending.length() + text.length() > MAX_QUEUE_CHARS) {
                int remove = Math.min(pending.length(), (pending.length() + text.length()) - MAX_QUEUE_CHARS);
                if (remove > 0) pending.delete(0, remove);
            }
            pending.append(text);
        }
        scheduleFlush();
    }

    void enqueueSessionHeader() {
        if (!isConfigured()) return;
        enqueue("\n=== IoT Inspector RO session ===\n" +
                "Android: " + Build.VERSION.RELEASE + " (SDK " + Build.VERSION.SDK_INT + ")\n" +
                "Device: " + safe(Build.MANUFACTURER) + " " + safe(Build.MODEL) + "\n" +
                "Mode: READ-ONLY NFC/BLE/GATT\n");
    }

    void flushNow() {
        if (!isConfigured() || closed) return;
        executor.execute(this::flushInternal);
    }

    private void scheduleFlush() {
        if (!flushScheduled.compareAndSet(false, true)) return;
        executor.schedule(() -> {
            flushScheduled.set(false);
            flushInternal();
        }, FLUSH_DELAY_MS, TimeUnit.MILLISECONDS);
    }

    private void flushInternal() {
        if (!isConfigured() || closed) return;
        String batch;
        synchronized (lock) {
            if (pending.length() == 0 && retryQueue.isEmpty()) return;
            StringBuilder all = new StringBuilder();
            while (!retryQueue.isEmpty()) all.append(retryQueue.removeFirst());
            all.append(pending);
            pending.setLength(0);
            batch = all.toString();
        }

        for (String chunk : split(batch, MAX_DISCORD_CONTENT)) {
            if (!postWithRetry(chunk)) {
                synchronized (lock) {
                    retryQueue.addLast(chunk);
                    while (queuedChars() > MAX_QUEUE_CHARS && !retryQueue.isEmpty()) {
                        retryQueue.removeFirst();
                    }
                }
                break;
            }
        }
    }

    private boolean postWithRetry(String content) {
        int[] delays = {0, 1200, 3000};
        for (int delay : delays) {
            if (closed) return false;
            if (delay > 0) {
                try {
                    Thread.sleep(delay);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    return false;
                }
            }
            HttpResult result = post(content);
            if (result.success) return true;
            if (result.status == 429 && result.retryAfterMs > 0) {
                try {
                    Thread.sleep(Math.min(result.retryAfterMs, 10_000L));
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    return false;
                }
            } else if (result.status >= 400 && result.status < 500) {
                return false;
            }
        }
        return false;
    }

    private HttpResult post(String content) {
        HttpURLConnection connection = null;
        try {
            URL url = new URL(webhookUrl + (webhookUrl.contains("?") ? "&" : "?") + "wait=true");
            connection = (HttpURLConnection) url.openConnection();
            connection.setConnectTimeout(8000);
            connection.setReadTimeout(10000);
            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            connection.setRequestProperty("User-Agent", "IoT-Inspector-RO/1.1");

            String body = "{\"content\":\"" + jsonEscape(content) +
                    "\",\"allowed_mentions\":{\"parse\":[]}}";
            byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
            connection.setFixedLengthStreamingMode(bytes.length);
            try (OutputStream output = connection.getOutputStream()) {
                output.write(bytes);
            }

            int status = connection.getResponseCode();
            String response = readResponse(status >= 200 && status < 400
                    ? connection.getInputStream()
                    : connection.getErrorStream());
            long retryAfter = parseRetryAfterMs(response, connection.getHeaderField("Retry-After"));
            return new HttpResult(status >= 200 && status < 300, status, retryAfter);
        } catch (Exception ignored) {
            return new HttpResult(false, -1, 0L);
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    private static String readResponse(InputStream input) {
        if (input == null) return "";
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(input, StandardCharsets.UTF_8))) {
            StringBuilder out = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null && out.length() < 8192) out.append(line);
            return out.toString();
        } catch (Exception ignored) {
            return "";
        }
    }

    private static long parseRetryAfterMs(String json, String header) {
        if (header != null) {
            try {
                double seconds = Double.parseDouble(header.trim());
                if (seconds > 0) return (long) Math.ceil(seconds * 1000.0);
            } catch (NumberFormatException ignored) {}
        }
        if (json == null) return 0L;
        int key = json.indexOf("\"retry_after\"");
        if (key < 0) return 0L;
        int colon = json.indexOf(':', key);
        if (colon < 0) return 0L;
        int end = colon + 1;
        while (end < json.length() && "0123456789.".indexOf(json.charAt(end)) < 0) end++;
        int start = end;
        while (end < json.length() && "0123456789.".indexOf(json.charAt(end)) >= 0) end++;
        if (start == end) return 0L;
        try {
            double value = Double.parseDouble(json.substring(start, end));
            return value < 100 ? (long) Math.ceil(value * 1000.0) : (long) Math.ceil(value);
        } catch (NumberFormatException ignored) {
            return 0L;
        }
    }

    private static String[] split(String source, int maxChars) {
        if (source == null || source.isEmpty()) return new String[0];
        int parts = (source.length() + maxChars - 1) / maxChars;
        String[] out = new String[parts];
        int start = 0;
        for (int i = 0; i < parts; i++) {
            int end = Math.min(source.length(), start + maxChars);
            if (end < source.length()) {
                int newline = source.lastIndexOf('\n', end);
                if (newline > start + maxChars / 2) end = newline + 1;
            }
            out[i] = source.substring(start, end);
            start = end;
        }
        if (start != source.length()) throw new IllegalStateException("split incomplete");
        return out;
    }

    private static String jsonEscape(String value) {
        StringBuilder out = new StringBuilder(value.length() + 32);
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            switch (c) {
                case '\\': out.append("\\\\"); break;
                case '"': out.append("\\\""); break;
                case '\b': out.append("\\b"); break;
                case '\f': out.append("\\f"); break;
                case '\n': out.append("\\n"); break;
                case '\r': out.append("\\r"); break;
                case '\t': out.append("\\t"); break;
                default:
                    if (c < 0x20) out.append(String.format(Locale.US, "\\u%04x", (int) c));
                    else out.append(c);
            }
        }
        return out.toString();
    }

    private int queuedChars() {
        int size = 0;
        for (String s : retryQueue) size += s.length();
        return size;
    }

    private static String safe(String value) {
        return value == null ? "?" : value.replace('\n', ' ').replace('\r', ' ');
    }

    @Override public void close() {
        if (closed) return;
        executor.execute(this::flushInternal);
        executor.shutdown();
        try {
            executor.awaitTermination(2500, TimeUnit.MILLISECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            closed = true;
            executor.shutdownNow();
        }
    }

    private static final class HttpResult {
        final boolean success;
        final int status;
        final long retryAfterMs;

        HttpResult(boolean success, int status, long retryAfterMs) {
            this.success = success;
            this.status = status;
            this.retryAfterMs = retryAfterMs;
        }
    }
}
