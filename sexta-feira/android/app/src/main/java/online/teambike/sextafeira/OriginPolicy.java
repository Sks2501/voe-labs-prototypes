package online.teambike.sextafeira;

import java.net.URI;

/** Exact origin comparison; no suffix matching, user-info or cleartext. */
public final class OriginPolicy {
    public static final String HOME = "https://sexta.teambike.online/";
    private OriginPolicy() {}
    public static boolean isTrusted(String value) {
        if (value == null) return false;
        try {
            URI uri = new URI(value);
            return "https".equalsIgnoreCase(uri.getScheme())
                && "sexta.teambike.online".equalsIgnoreCase(uri.getHost())
                && uri.getRawUserInfo() == null && (uri.getPort() == -1 || uri.getPort() == 443);
        } catch (Exception error) { return false; }
    }
}
