package online.teambike.sextafeira;

import android.app.Activity;
import android.content.Intent;
import android.content.res.Configuration;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.tts.TextToSpeech;
import android.speech.tts.Voice;
import android.view.Gravity;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.webkit.*;
import android.widget.*;
import java.io.ByteArrayInputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.json.JSONObject;

/** Small Android client. The model and personal database remain on the owner's server. */
public class MainActivity extends Activity {
    private static final int EXPORT_REQUEST = 41;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final ExecutorService writer = Executors.newSingleThreadExecutor();
    private FrameLayout root;
    private WebView web;
    private LinearLayout status;
    private TextView statusTitle, statusMessage;
    private ProgressBar progress;
    private Button retry;
    private TextToSpeech speech;
    private volatile boolean localVoiceReady = false;
    private volatile boolean systemDark = false;
    private int surfaceBackground = Color.WHITE;
    private byte[] pendingExport;
    private boolean destroyed = false;
    private boolean mainFrameFailed = false;
    private final Runnable loadingTimeout = () -> showError("O servidor demorou a responder", "Confira sua conexão e tente novamente.");

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        systemDark=(getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK)==Configuration.UI_MODE_NIGHT_YES;
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        root = new FrameLayout(this);
        root.setBackgroundColor(Color.rgb(13,21,32));
        setContentView(root);
        if (Build.VERSION.SDK_INT >= 30) {
            getWindow().setDecorFitsSystemWindows(false);
            getWindow().setStatusBarColor(Color.TRANSPARENT);
            getWindow().setNavigationBarColor(Color.TRANSPARENT);
            root.setOnApplyWindowInsetsListener((view, insets) -> {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
                android.graphics.Insets keyboard = insets.getInsets(WindowInsets.Type.ime());
                view.setPadding(bars.left,bars.top,bars.right,Math.max(bars.bottom,keyboard.bottom));
                return WindowInsets.CONSUMED;
            });
        }
        createStatus();
        applySurface(systemDark ? "dark" : "light");
        createWebView();
        speech = new TextToSpeech(this, result -> ui.post(() -> configureVoice(result)));
        loadHome();
    }

    private void createStatus() {
        status = new LinearLayout(this);
        status.setOrientation(LinearLayout.VERTICAL);status.setGravity(Gravity.CENTER);
        int space = dp(28);status.setPadding(space,space,space,space);
        status.setBackgroundColor(Color.rgb(13,21,32));
        TextView symbol = new TextView(this);symbol.setText("S✧");symbol.setTextColor(Color.rgb(166,239,238));symbol.setTextSize(36);
        status.addView(symbol);
        statusTitle = new TextView(this);statusTitle.setTextColor(Color.WHITE);statusTitle.setTextSize(21);statusTitle.setGravity(Gravity.CENTER);
        status.addView(statusTitle,new LinearLayout.LayoutParams(-1,-2));
        statusMessage = new TextView(this);statusMessage.setTextColor(Color.rgb(170,187,201));statusMessage.setTextSize(14);statusMessage.setGravity(Gravity.CENTER);statusMessage.setPadding(0,dp(14),0,dp(20));
        status.addView(statusMessage,new LinearLayout.LayoutParams(-1,-2));
        progress = new ProgressBar(this);status.addView(progress,new LinearLayout.LayoutParams(dp(32),dp(32)));
        retry = new Button(this);retry.setText("Tentar novamente");retry.setOnClickListener(view -> loadHome());status.addView(retry);
        root.addView(status,new FrameLayout.LayoutParams(-1,-1));
    }

    @SuppressWarnings("deprecation") private void createWebView() {
        web = new WebView(this);web.setBackgroundColor(surfaceBackground);
        WebView.setWebContentsDebuggingEnabled(false);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);settings.setAllowContentAccess(false);
        settings.setAllowFileAccessFromFileURLs(false);settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);settings.setSupportMultipleWindows(false);
        settings.setMediaPlaybackRequiresUserGesture(true);settings.setCacheMode(WebSettings.LOAD_NO_CACHE);
        settings.setSafeBrowsingEnabled(true);
        settings.setUserAgentString(settings.getUserAgentString()+" SextaFeiraAndroid/1.0.2");
        if(Build.VERSION.SDK_INT>=29)settings.setForceDark(WebSettings.FORCE_DARK_OFF);
        if(Build.VERSION.SDK_INT>=33)settings.setAlgorithmicDarkeningAllowed(false);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web,false);
        web.addJavascriptInterface(new LocalActions(),"SextaAndroid");
        web.setWebChromeClient(new WebChromeClient() {
            @Override public void onPermissionRequest(PermissionRequest request) { request.deny(); }
            @Override public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback callback) { callback.invoke(origin,false,false); }
        });
        web.setDownloadListener((url,agent,disposition,mime,length) -> {
            if (OriginPolicy.isTrusted(url)) {
                try { startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(url))); }
                catch (Exception ignored) { toast("Não há navegador disponível para esse download."); }
            } else toast("Use Exportar meus dados nos Ajustes.");
        });
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (OriginPolicy.isTrusted(request.getUrl().toString())) return false;
                if(OriginPolicy.shouldOpenExternal(request.getUrl().toString(),request.getMethod(),request.isForMainFrame(),request.hasGesture())){
                    try{startActivity(new Intent(Intent.ACTION_VIEW,request.getUrl()).addCategory(Intent.CATEGORY_BROWSABLE));}
                    catch(Exception ignored){toast("Não há navegador disponível para abrir esta fonte.");}
                }
                // Keep all other origins/schemes outside the authenticated WebView.
                return true;
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest request) {
                if (!OriginPolicy.isTrusted(request.getUrl().toString()))
                    return new WebResourceResponse("text/plain","UTF-8",403,"Blocked",null,new ByteArrayInputStream(new byte[0]));
                return null;
            }
            @Override public void onPageStarted(WebView view,String url,android.graphics.Bitmap icon) {
                if (!OriginPolicy.isTrusted(url)) { view.stopLoading();showError("Endereço não permitido","Este app acessa somente o servidor da SEXTA-FEIRA."); }
            }
            @Override public void onPageFinished(WebView view,String url) {
                if (OriginPolicy.isTrusted(url) && !mainFrameFailed) { ui.removeCallbacks(loadingTimeout);status.setVisibility(View.GONE);view.setVisibility(View.VISIBLE);notifyVoice(); }
            }
            @Override public void onReceivedSslError(WebView view,SslErrorHandler handler,SslError error) {
                handler.cancel();showError("Não foi possível validar a conexão segura","O certificado precisa ser válido. Nenhuma proteção foi desativada.");
            }
            @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error) {
                if(request.isForMainFrame())showError("Sem conexão com a SEXTA-FEIRA","Confira sua Internet e a disponibilidade do servidor.");
            }
            @Override public void onReceivedHttpError(WebView view,WebResourceRequest request,WebResourceResponse response) {
                if(request.isForMainFrame() && response.getStatusCode()>=400)showError("O servidor está indisponível","Tente novamente em instantes. Seus dados permanecem no servidor.");
            }
            @Override public boolean onRenderProcessGone(WebView view,RenderProcessGoneDetail detail) {
                view.removeJavascriptInterface("SextaAndroid");root.removeView(view);view.destroy();web=null;
                showError("Vamos reabrir a interface","O Android encerrou a tela para liberar memória. Entre novamente se necessário.");return true;
            }
        });
        root.addView(web,0,new FrameLayout.LayoutParams(-1,-1));
    }

    private void loadHome() {
        mainFrameFailed=false;
        if(web==null)createWebView();
        statusTitle.setText("SEXTA-FEIRA");statusMessage.setText("Conectando ao seu servidor privado…");
        progress.setVisibility(View.VISIBLE);retry.setVisibility(View.GONE);status.setVisibility(View.VISIBLE);
        web.setVisibility(View.INVISIBLE);ui.removeCallbacks(loadingTimeout);ui.postDelayed(loadingTimeout,30000);
        web.loadUrl(OriginPolicy.HOME);
    }
    private void showError(String title,String message) {
        if(destroyed)return;mainFrameFailed=true;ui.removeCallbacks(loadingTimeout);statusTitle.setText(title);statusMessage.setText(message);
        progress.setVisibility(View.GONE);retry.setVisibility(View.VISIBLE);status.setVisibility(View.VISIBLE);
    }
    private int dp(int value) { return (int)(value*getResources().getDisplayMetrics().density+0.5f); }
    private void toast(String text) { Toast.makeText(this,text,Toast.LENGTH_LONG).show(); }

    private void applySurface(String theme) {
        boolean dark="dark".equals(theme);
        surfaceBackground=dark ? Color.rgb(16,16,16) : Color.WHITE;
        root.setBackgroundColor(surfaceBackground);status.setBackgroundColor(surfaceBackground);
        statusTitle.setTextColor(dark ? Color.WHITE : Color.rgb(23,23,23));
        statusMessage.setTextColor(dark ? Color.rgb(170,170,170) : Color.rgb(110,110,110));
        progress.setIndeterminateTintList(ColorStateList.valueOf(dark ? Color.WHITE : Color.BLACK));
        retry.setTextColor(dark ? Color.WHITE : Color.BLACK);
        if(web!=null)web.setBackgroundColor(surfaceBackground);
        if(Build.VERSION.SDK_INT>=30) {
            android.view.WindowInsetsController controller=getWindow().getInsetsController();
            int flags=android.view.WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS | android.view.WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;
            if(controller!=null)controller.setSystemBarsAppearance(dark ? 0 : flags,flags);
        } else {
            int flags=View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR | View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
            int value=getWindow().getDecorView().getSystemUiVisibility();
            getWindow().getDecorView().setSystemUiVisibility(dark ? value & ~flags : value | flags);
            getWindow().setStatusBarColor(surfaceBackground);getWindow().setNavigationBarColor(surfaceBackground);
        }
    }
    @Override public void onConfigurationChanged(Configuration config) {
        super.onConfigurationChanged(config);
        systemDark=(config.uiMode & Configuration.UI_MODE_NIGHT_MASK)==Configuration.UI_MODE_NIGHT_YES;
        if(web!=null && OriginPolicy.isTrusted(web.getUrl()))web.evaluateJavascript("window.dispatchEvent(new Event('sexta-native-theme'));",null);
    }

    private void configureVoice(int result) {
        if(destroyed || speech==null || result!=TextToSpeech.SUCCESS)return;
        try {
            Voice selected=null;
            for(Voice voice:speech.getVoices()) {
                if("pt".equals(voice.getLocale().getLanguage()) && !voice.isNetworkConnectionRequired()) {
                    if(selected==null || "BR".equals(voice.getLocale().getCountry()))selected=voice;
                }
            }
            localVoiceReady=selected!=null && speech.setVoice(selected)==TextToSpeech.SUCCESS;
            notifyVoice();
        } catch(Exception ignored) { localVoiceReady=false; }
    }
    private void notifyVoice() {
        if(web!=null && OriginPolicy.isTrusted(web.getUrl()))web.evaluateJavascript("window.dispatchEvent(new Event('sexta-native-voice'));",null);
    }
    public final class LocalActions {
        @JavascriptInterface public String getSystemTheme() { return systemDark ? "dark" : "light"; }
        @JavascriptInterface public void updateSurface(String theme) {
            if(!"light".equals(theme) && !"dark".equals(theme))return;
            ui.post(() -> {if(!destroyed && web!=null && OriginPolicy.isTrusted(web.getUrl()))applySurface(theme);});
        }
        @JavascriptInterface public boolean hasLocalVoice() { return localVoiceReady; }
        @JavascriptInterface public void speak(String text,float rate) {
            if(text==null || text.length()>6000 || Float.isNaN(rate) || rate<0.5f || rate>2f)return;
            ui.post(() -> { if(!destroyed && web!=null && OriginPolicy.isTrusted(web.getUrl()) && localVoiceReady) {
                speech.setSpeechRate(rate);speech.speak(text,TextToSpeech.QUEUE_FLUSH,null,"sexta-reply");
            }});
        }
        @JavascriptInterface public void stopSpeech() { ui.post(() -> { if(speech!=null)speech.stop(); }); }
        @JavascriptInterface public void exportJson(String text) {
            if(text==null || text.length()>5*1024*1024)return;
            try {
                JSONObject object=new JSONObject(text);
                if(object.optInt("schema_version")!=2 || !object.has("messages") || !object.has("preferences"))return;
                byte[] bytes=text.getBytes(StandardCharsets.UTF_8);if(bytes.length>5*1024*1024)return;
                ui.post(() -> { if(destroyed || web==null || !OriginPolicy.isTrusted(web.getUrl()) || pendingExport!=null)return;
                    pendingExport=bytes;
                    Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/json");
                    intent.putExtra(Intent.EXTRA_TITLE,"sexta-feira-dados-"+new SimpleDateFormat("yyyy-MM-dd",Locale.ROOT).format(new Date())+".json");
                    try { startActivityForResult(intent,EXPORT_REQUEST); }catch(Exception ignored){pendingExport=null;toast("Não foi possível abrir o seletor de arquivos.");}
                });
            } catch(Exception ignored) { }
        }
    }
    @Override protected void onActivityResult(int request,int result,Intent data) {
        super.onActivityResult(request,result,data);
        if(request!=EXPORT_REQUEST)return;
        byte[] payload=pendingExport;pendingExport=null;
        if(result!=RESULT_OK || data==null || data.getData()==null || payload==null)return;
        final Uri uri=data.getData();
        writer.execute(() -> {
            try(OutputStream output=getContentResolver().openOutputStream(uri,"wt")) {
                if(output==null)throw new java.io.IOException("No output stream");output.write(payload);output.flush();
                ui.post(() -> {if(!destroyed)toast("Exportação salva no local escolhido.");});
            } catch(Exception ignored) {ui.post(() -> {if(!destroyed)toast("Não foi possível salvar a exportação.");});}
        });
    }
    @Override public void onBackPressed() {
        if(web==null || !OriginPolicy.isTrusted(web.getUrl())) { moveTaskToBack(true);return; }
        String action="(function(){const d=document.querySelector('dialog[open]');if(d){d.close();return true;}if(document.body.classList.contains('sidebar-open')){document.getElementById('close-sidebar').click();return true;}const c=document.getElementById('view-chat');if(c&&c.hidden){document.querySelector('[data-view=chat]').click();return true;}return false;})()";
        web.evaluateJavascript(action,result -> {if(!"true".equals(result))moveTaskToBack(true);});
    }
    @Override protected void onPause() { if(speech!=null)speech.stop();super.onPause(); }
    @Override protected void onDestroy() {
        destroyed=true;ui.removeCallbacksAndMessages(null);localVoiceReady=false;pendingExport=null;writer.shutdown();
        if(speech!=null){speech.stop();speech.shutdown();speech=null;}
        if(web!=null){web.stopLoading();web.removeJavascriptInterface("SextaAndroid");root.removeView(web);web.clearCache(true);web.destroy();web=null;}
        super.onDestroy();
    }
}
