package online.teambike.sextafeira;

import java.net.URI;

/** Exact origin comparison; no suffix matching, user-info or cleartext. */
public final class OriginPolicy {
    public static final String HOME = "https://sexta.teambike.online/";
    private OriginPolicy() {}
    public static boolean shouldOpenExternal(String value,String method,boolean mainFrame,boolean userGesture) {
        return mainFrame && userGesture && "GET".equals(method) && isExternalSource(value);
    }
    public static boolean isExternalSource(String value) {
        if(value==null || value.length()>1600 || value.matches(".*[\\s\\\\].*"))return false;
        try{
            URI uri=new URI(value);String host=uri.getHost();
            if(!"https".equalsIgnoreCase(uri.getScheme()) || host==null || uri.getRawUserInfo()!=null || (uri.getPort()!=-1 && uri.getPort()!=443))return false;
            host=host.toLowerCase(java.util.Locale.ROOT);
            String query=uri.getQuery();
            if(query!=null && java.util.regex.Pattern.compile("(?:^|&)(?:token|access_token|password|passwd|secret|api_key|apikey|authorization|session)=",java.util.regex.Pattern.CASE_INSENSITIVE).matcher(query).find())return false;
            return !isTrusted(value) && host.contains(".") && !host.endsWith(".") && !host.contains(":")
                && !host.matches("(?:0x[0-9a-f]+|[0-9]+)(?:\\.(?:0x[0-9a-f]+|[0-9]+))*")
                && !host.endsWith(".local") && !host.endsWith(".localhost") && !host.endsWith(".internal")
                && !host.endsWith(".lan") && !host.endsWith(".home") && !host.endsWith(".arpa");
        }catch(Exception error){return false;}
    }
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
