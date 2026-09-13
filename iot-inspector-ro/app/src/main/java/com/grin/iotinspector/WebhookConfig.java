package com.grin.iotinspector;

import android.content.Context;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;

final class WebhookConfig {
    private WebhookConfig() {}

    static String load(Context context) {
        if (context == null) return "";
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                context.getAssets().open("webhook.txt"), StandardCharsets.UTF_8))) {
            String line = reader.readLine();
            if (line == null) return "";
            String value = line.trim();
            if (value.startsWith("https://discord.com/api/webhooks/") ||
                    value.startsWith("https://discordapp.com/api/webhooks/")) {
                return value;
            }
            return "";
        } catch (Exception ignored) {
            return "";
        }
    }
}
