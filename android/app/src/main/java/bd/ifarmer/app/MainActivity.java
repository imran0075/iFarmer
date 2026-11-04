package bd.ifarmer.app;

import android.app.Activity;
import android.os.Bundle;
import android.os.Build;
import android.Manifest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.GeolocationPermissions;
import android.webkit.ValueCallback;
import android.webkit.JavascriptInterface;
import android.net.Uri;
import android.content.Intent;
import android.content.ClipData;
import android.content.pm.PackageManager;
import android.provider.MediaStore;
import android.graphics.Color;
import android.view.View;
import android.widget.Toast;
import com.google.firebase.messaging.FirebaseMessaging;

import androidx.core.content.ContextCompat;
import androidx.core.content.FileProvider;

import java.io.File;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

public class MainActivity extends Activity {
    private static final String HOME = "https://ifarmer.onrender.com/";
    private static final int LOCATION_PERMISSION_REQUEST = 4101;
    private static final int FILE_CHOOSER_REQUEST = 4102;
    private static final int NOTIFICATION_PERMISSION_REQUEST = 4103;
    private static final int CAMERA_PERMISSION_REQUEST = 4104;

    private WebView webView;
    private ValueCallback<Uri[]> filePathCallback;
    private Uri cameraPhotoUri;
    private GeolocationPermissions.Callback pendingGeoCallback;
    private String pendingGeoOrigin;
    private boolean pendingCameraChooser;

    @JavascriptInterface
    public void shareApp() {
        String url = "https://ifarmer.onrender.com/static/download.html";
        Intent send = new Intent(Intent.ACTION_SEND);
        send.setType("text/plain");
        send.putExtra(Intent.EXTRA_SUBJECT, "iFarmer অ্যাপ");
        send.putExtra(Intent.EXTRA_TEXT, "কৃষির ডিজিটাল সহযাত্রী iFarmer অ্যাপ ডাউনলোড করুন:\n" + url);
        startActivity(Intent.createChooser(send, "iFarmer শেয়ার করুন"));
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.rgb(23, 107, 69));
        getWindow().setNavigationBarColor(Color.rgb(23, 107, 69));

        webView = new WebView(this);
        webView.setBackgroundColor(Color.WHITE);
        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.getSettings().setGeolocationEnabled(true);
        webView.getSettings().setAllowFileAccess(true);
        webView.getSettings().setSupportZoom(false);
        webView.addJavascriptInterface(this, "iFarmerNative");

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onGeolocationPermissionsShowPrompt(String origin,
                    GeolocationPermissions.Callback callback) {
                if (hasLocationPermission()) {
                    callback.invoke(origin, true, false);
                } else {
                    pendingGeoOrigin = origin;
                    pendingGeoCallback = callback;
                    requestLocationPermission();
                }
            }

            @Override
            public boolean onShowFileChooser(WebView view,
                    ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (filePathCallback != null) filePathCallback.onReceiveValue(null);
                filePathCallback = callback;
                if (ContextCompat.checkSelfPermission(MainActivity.this, Manifest.permission.CAMERA)
                        == PackageManager.PERMISSION_GRANTED) {
                    openImagePicker(true);
                } else {
                    pendingCameraChooser = true;
                    requestPermissions(new String[] { Manifest.permission.CAMERA }, CAMERA_PERMISSION_REQUEST);
                }
                return true;
            }
        });

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                view.evaluateJavascript("(function(){if(document.getElementById('ifarmer-share-app'))return;var b=document.createElement('button');b.id='ifarmer-share-app';b.type='button';b.textContent='↗ অ্যাপ শেয়ার করুন';b.setAttribute('aria-label','iFarmer অ্যাপ শেয়ার করুন');b.style.cssText='position:fixed;right:14px;bottom:78px;z-index:99999;border:0;border-radius:24px;padding:12px 17px;background:#176b45;color:white;font-weight:700;font-size:14px;box-shadow:0 4px 14px #0003';b.onclick=function(){if(window.iFarmerNative&&window.iFarmerNative.shareApp){window.iFarmerNative.shareApp()}else if(navigator.share){navigator.share({title:'iFarmer অ্যাপ',text:'কৃষির ডিজিটাল সহযাত্রী iFarmer অ্যাপ ডাউনলোড করুন',url:'https://ifarmer.onrender.com/static/download.html'}).catch(function(){})}};document.body.appendChild(b)})()", null);
            }
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                String host = uri.getHost();
                if ("ifarmer.onrender.com".equals(host)) return false;

                String scheme = uri.getScheme();
                if ("http".equals(scheme) || "https".equals(scheme)
                        || "tel".equals(scheme) || "mailto".equals(scheme)) {
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, uri));
                    } catch (Exception e) {
                        Toast.makeText(MainActivity.this,
                                "এই লিংকটি খোলা যাচ্ছে না", Toast.LENGTH_SHORT).show();
                    }
                }
                return true;
            }
        });

        setContentView(webView);
        if (savedInstanceState == null) webView.loadUrl(HOME);
        else webView.restoreState(savedInstanceState);

        requestNotificationPermission();
        FirebaseMessaging.getInstance().subscribeToTopic("ifarmer_all");
    }

    private void requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33
                && ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[] { Manifest.permission.POST_NOTIFICATIONS },
                    NOTIFICATION_PERMISSION_REQUEST);
        }
    }

    private boolean hasLocationPermission() {
        return ContextCompat.checkSelfPermission(this,
                android.Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
                || ContextCompat.checkSelfPermission(this,
                android.Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    private void requestLocationPermission() {
        requestPermissions(new String[] {
                android.Manifest.permission.ACCESS_FINE_LOCATION,
                android.Manifest.permission.ACCESS_COARSE_LOCATION
        }, LOCATION_PERMISSION_REQUEST);
    }

    private void openImagePicker(boolean includeCamera) {
        Intent galleryIntent = new Intent(Intent.ACTION_GET_CONTENT);
        galleryIntent.setType("image/*");
        galleryIntent.addCategory(Intent.CATEGORY_OPENABLE);

        Intent cameraIntent = null;
        try {
            if (!includeCamera) throw new SecurityException("Camera permission not granted");
            File cameraDir = new File(getCacheDir(), "camera");
            if (!cameraDir.exists()) cameraDir.mkdirs();
            String fileName = "ifarmer_" +
                    new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(new Date()) + ".jpg";
            File photoFile = new File(cameraDir, fileName);
            cameraPhotoUri = FileProvider.getUriForFile(this,
                    getPackageName() + ".fileprovider", photoFile);

            cameraIntent = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
            cameraIntent.putExtra(MediaStore.EXTRA_OUTPUT, cameraPhotoUri);
            cameraIntent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                    | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            cameraIntent.setClipData(ClipData.newUri(getContentResolver(), "iFarmer camera photo", cameraPhotoUri));
        } catch (Exception e) {
            cameraPhotoUri = null;
        }

        Intent chooser = Intent.createChooser(galleryIntent, "ছবি নির্বাচন করুন");
        if (cameraIntent != null) {
            chooser.putExtra(Intent.EXTRA_INITIAL_INTENTS, new Intent[] { cameraIntent });
            chooser.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            chooser.setClipData(ClipData.newUri(getContentResolver(), "iFarmer camera photo", cameraPhotoUri));
        }
        try {
            startActivityForResult(chooser, FILE_CHOOSER_REQUEST);
        } catch (Exception e) {
            if (filePathCallback != null) filePathCallback.onReceiveValue(null);
            filePathCallback = null;
            Toast.makeText(this, "ছবি নির্বাচন করা যাচ্ছে না", Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_CHOOSER_REQUEST && filePathCallback != null) {
            Uri[] results = null;
            if (resultCode == RESULT_OK) {
                Uri selected = data != null ? data.getData() : null;
                if (selected != null) results = new Uri[] { selected };
                else if (cameraPhotoUri != null) results = new Uri[] { cameraPhotoUri };
            }
            filePathCallback.onReceiveValue(results);
            filePathCallback = null;
            cameraPhotoUri = null;
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == CAMERA_PERMISSION_REQUEST && pendingCameraChooser) {
            pendingCameraChooser = false;
            boolean cameraGranted = ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
                    == PackageManager.PERMISSION_GRANTED;
            openImagePicker(cameraGranted);
            if (!cameraGranted) {
                Toast.makeText(this, "ক্যামেরার অনুমতি না দিলে গ্যালারি থেকে ছবি নিতে পারবেন", Toast.LENGTH_LONG).show();
            }
        }
        if (requestCode == LOCATION_PERMISSION_REQUEST && pendingGeoCallback != null) {
            boolean granted = hasLocationPermission();
            pendingGeoCallback.invoke(pendingGeoOrigin, granted, false);
            pendingGeoCallback = null;
            pendingGeoOrigin = null;
            if (!granted) {
                Toast.makeText(this, "লোকেশন ব্যবহার করতে GPS অনুমতি দিন", Toast.LENGTH_LONG).show();
            }
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        if (webView != null) webView.saveState(outState);
        super.onSaveInstanceState(outState);
    }

    @Override
    protected void onDestroy() {
        if (filePathCallback != null) filePathCallback.onReceiveValue(null);
        if (webView != null) webView.destroy();
        super.onDestroy();
    }
}
