package com.doorwin.app;

import android.app.Activity;
import android.content.ContentValues;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.media.MediaScannerConnection;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.view.Gravity;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.TextView;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.io.PrintWriter;
import java.io.StringWriter;

/**
 * 小贤门窗 App 外壳：
 * 全屏 WebView 直接加载打包在 assets 里的本地网页（无需网络、无需服务器），
 * 并提供 Android.saveImage() 接口把导出图片保存到手机相册。
 * 任何启动异常都会显示在屏幕上（红底文字），方便排查。
 */
public class MainActivity extends Activity {

    private WebView webView;
    private TextView splash;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // 全局兜底：未捕获异常显示在屏幕上，而不是直接闪退
        Thread.setDefaultUncaughtExceptionHandler(new Thread.UncaughtExceptionHandler() {
            @Override
            public void uncaughtException(Thread thread, final Throwable t) {
                try {
                    runOnUiThread(new Runnable() {
                        @Override
                        public void run() {
                            showError(t);
                        }
                    });
                    Thread.sleep(10000); // 留时间让用户看清错误
                } catch (Exception e) { /* ignore */ }
                System.exit(2);
            }
        });
        try {
            startApp();
        } catch (Throwable t) {
            showError(t);
        }
    }

    private void startApp() {
        WebView.setWebContentsDebuggingEnabled(true); // 允许 adb 远程调试
        webView = new WebView(this);
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);       // localStorage：自建款式/价格配置可持久化
        s.setAllowFileAccess(true);         // 允许读取 assets 内本地文件
        s.setAllowContentAccess(true);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setSupportZoom(false);
        webView.setBackgroundColor(Color.parseColor("#0f1722"));

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView view, int errorCode,
                                        String description, String failingUrl) {
                // 页面加载错误：显示原因而不是白屏
                view.loadData("<html><body style='background:#300000;color:#fff;font-family:sans-serif;padding:24px'>" +
                        "<h2>页面加载失败</h2><p>" + description + "</p></body></html>",
                        "text/html", "UTF-8");
            }
        });

        webView.addJavascriptInterface(new AndroidBridge(), "Android");

        // 启动屏：WebView 之上盖一层进度文字，便于定位闪退环节
        splash = new TextView(this);
        splash.setBackgroundColor(Color.parseColor("#0f1722"));
        splash.setTextColor(Color.WHITE);
        splash.setGravity(Gravity.CENTER);
        splash.setText("小贤门窗\n正在启动…");
        FrameLayout root = new FrameLayout(this);
        root.addView(webView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        root.addView(splash, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        setContentView(root);
        webView.loadUrl("file:///android_asset/index.html");
    }

    /** 红底显示异常堆栈，用户可截图/复制反馈 */
    private void showError(Throwable t) {
        StringWriter sw = new StringWriter();
        t.printStackTrace(new PrintWriter(sw));
        TextView tv = new TextView(this);
        tv.setTextColor(Color.WHITE);
        tv.setBackgroundColor(Color.parseColor("#300000"));
        tv.setPadding(40, 40, 40, 40);
        tv.setText("启动失败，请截图或复制以下内容反馈：\n\n" + sw.toString());
        tv.setTextIsSelectable(true);
        setContentView(tv);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    /** JS 桥：Android.saveImage(dataUrl) → 保存到相册，返回 "OK|位置" 或 "ERR|原因" */
    public class AndroidBridge {

        /** JS 桥：更新/隐藏启动屏文字 */
        @JavascriptInterface
        public void setSplash(final String text, final boolean hide) {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    if (splash == null) return;
                    if (hide) {
                        splash.setVisibility(View.GONE);
                    } else {
                        splash.setVisibility(View.VISIBLE);
                        splash.setText(text);
                    }
                }
            });
        }

        @JavascriptInterface
        public String saveImage(String dataUrl) {
            try {
                String b64 = dataUrl.substring(dataUrl.indexOf(',') + 1);
                byte[] bytes = Base64.decode(b64, Base64.DEFAULT);
                Bitmap bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
                if (bmp == null) return "ERR|图片解码失败";

                String fileName = "小贤门窗_" + System.currentTimeMillis() + ".png";
                if (Build.VERSION.SDK_INT >= 29) {
                    // Android 10+：直接写入相册（无需权限）
                    ContentValues v = new ContentValues();
                    v.put(MediaStore.Images.Media.DISPLAY_NAME, fileName);
                    v.put(MediaStore.Images.Media.MIME_TYPE, "image/png");
                    v.put(MediaStore.Images.Media.RELATIVE_PATH,
                            Environment.DIRECTORY_PICTURES + "/小贤门窗");
                    Uri uri = getContentResolver().insert(
                            MediaStore.Images.Media.EXTERNAL_CONTENT_URI, v);
                    if (uri == null) return "ERR|相册写入失败";
                    OutputStream out = getContentResolver().openOutputStream(uri);
                    bmp.compress(Bitmap.CompressFormat.PNG, 100, out);
                    out.close();
                    return "OK|相册/Pictures/小贤门窗";
                } else {
                    // Android 8-9：保存到应用图片目录（免权限），并通知相册扫描
                    File dir = getExternalFilesDir(Environment.DIRECTORY_PICTURES);
                    File f = new File(dir, fileName);
                    FileOutputStream out = new FileOutputStream(f);
                    bmp.compress(Bitmap.CompressFormat.PNG, 100, out);
                    out.close();
                    MediaScannerConnection.scanFile(MainActivity.this,
                            new String[]{f.getAbsolutePath()}, null, null);
                    return "OK|" + f.getAbsolutePath();
                }
            } catch (Exception e) {
                return "ERR|" + e.getMessage();
            }
        }
    }
}
