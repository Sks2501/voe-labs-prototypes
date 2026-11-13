package online.teambike.sextafeira;

public final class OriginPolicyTest {
    public static void main(String[] args) {
        String[] allowed={OriginPolicy.HOME,"https://sexta.teambike.online:443/api/v1/health","https://SEXTA.TEAMBIKE.ONLINE/"};
        String[] blocked={null,"http://sexta.teambike.online/","https://sexta.teambike.online.evil.invalid/",
            "https://evilsexta.teambike.online/","https://user@sexta.teambike.online/","https://sexta.teambike.online:444/",
            "file:///data/data/secret","content://private","javascript:alert(1)","about:blank","https://sexta.teambike.online@evil.invalid/"};
        for(String url:allowed)if(!OriginPolicy.isTrusted(url))throw new AssertionError("Trusted URL rejected");
        for(String url:blocked)if(OriginPolicy.isTrusted(url))throw new AssertionError("Untrusted URL accepted");
        String[] sources={"https://docs.python.org/3/","https://www.gov.br/","https://example.com:443/article"};
        String[] badSources={OriginPolicy.HOME,"http://example.com/","javascript:alert(1)","https://127.0.0.1/","https://192.168.0.1/","https://machine.local/","https://user@example.com/","https://example.com:444/",
            "https://machine.local./","https://machine.internal./","https://example.com./","https://0x7f.0.0.1/","https://0177.0.0.1/",
            "https://example.com/?token=secret","https://example.com/?ACCESS_TOKEN=secret","https://example.com/?%74oken=secret"};
        for(String url:sources)if(!OriginPolicy.isExternalSource(url))throw new AssertionError("Source URL rejected");
        for(String url:badSources)if(OriginPolicy.isExternalSource(url))throw new AssertionError("Unsafe source URL accepted");
        String external="https://docs.python.org/3/";
        if(!OriginPolicy.shouldOpenExternal(external,"GET",true,true))throw new AssertionError("Explicit source click rejected");
        if(OriginPolicy.shouldOpenExternal(external,"GET",true,false))throw new AssertionError("Automatic navigation accepted");
        if(OriginPolicy.shouldOpenExternal(external,"GET",false,true))throw new AssertionError("Subframe navigation accepted");
        if(OriginPolicy.shouldOpenExternal(external,"POST",true,true))throw new AssertionError("Form submission accepted");
        if(OriginPolicy.shouldOpenExternal(OriginPolicy.HOME,"GET",true,true))throw new AssertionError("Trusted origin left WebView");
        System.out.println("Origin policy: "+(allowed.length+blocked.length+sources.length+badSources.length+5)+" checks passed");
    }
}
