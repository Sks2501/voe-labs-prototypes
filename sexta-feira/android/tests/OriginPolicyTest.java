package online.teambike.sextafeira;

public final class OriginPolicyTest {
    public static void main(String[] args) {
        String[] allowed={OriginPolicy.HOME,"https://sexta.teambike.online:443/api/v1/health","https://SEXTA.TEAMBIKE.ONLINE/"};
        String[] blocked={null,"http://sexta.teambike.online/","https://sexta.teambike.online.evil.invalid/",
            "https://evilsexta.teambike.online/","https://user@sexta.teambike.online/","https://sexta.teambike.online:444/",
            "file:///data/data/secret","content://private","javascript:alert(1)","about:blank","https://sexta.teambike.online@evil.invalid/"};
        for(String url:allowed)if(!OriginPolicy.isTrusted(url))throw new AssertionError("Trusted URL rejected");
        for(String url:blocked)if(OriginPolicy.isTrusted(url))throw new AssertionError("Untrusted URL accepted");
        System.out.println("Origin policy: "+(allowed.length+blocked.length)+" checks passed");
    }
}
