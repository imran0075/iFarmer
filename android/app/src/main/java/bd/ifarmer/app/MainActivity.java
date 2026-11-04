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
import android.widget.Button;
import android.widget.FrameLayout;
import android.view.Gravity;
import android.view.ViewGroup;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Looper;
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
    private boolean locationPermissionRequestActive;
    private LocationManager locationManager;
    private LocationListener nativeLocationListener;
    private String pendingNativeCallback;

    @JavascriptInterface
    public void getCurrentLocation(String callbackName) {
        pendingNativeCallback = callbackName;
        runOnUiThread(() -> {
            if (!hasLocationPermission()) {
                requestLocationPermission();
                sendLocationError("permission");
                return;
            }
            try {
                locationManager = (LocationManager) getSystemService(LOCATION_SERVICE);
                boolean gps = locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER);
                boolean network = locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER);
                if (!gps && !network) { sendLocationError("gps_off"); return; }
                Location best = null;
                if (gps) best = locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER);
                if (best == null && network) best = locationManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER);
                if (best != null && System.currentTimeMillis() - best.getTime() < 120000) {
                    sendLocationSuccess(best);
                    return;
                }
                if (nativeLocationListener != null) locationManager.removeUpdates(nativeLocationListener);
                nativeLocationListener = new LocationListener() {
                    @Override public void onLocationChanged(Location location) {
                        locationManager.removeUpdates(this);
                        nativeLocationListener = null;
                        sendLocationSuccess(location);
                    }
                    @Override public void onProviderDisabled(String provider) {}
                    @Override public void onProviderEnabled(String provider) {}
                    @Override public void onStatusChanged(String provider, int status, android.os.Bundle extras) {}
                };
                if (gps) locationManager.requestLocationUpdates(LocationManager.GPS_PROVIDER, 1000L, 0f, nativeLocationListener, Looper.getMainLooper());
                if (network) locationManager.requestLocationUpdates(LocationManager.NETWORK_PROVIDER, 1000L, 0f, nativeLocationListener, Looper.getMainLooper());
                webView.postDelayed(() -> {
                    if (nativeLocationListener != null) {
                        locationManager.removeUpdates(nativeLocationListener);
                        nativeLocationListener = null;
                        sendLocationError("timeout");
                    }
                }, 25000);
            } catch (SecurityException e) { sendLocationError("permission"); }
              catch (Exception e) { sendLocationError("unavailable"); }
        });
    }

    private void sendLocationSuccess(Location location) {
        if (location == null || webView == null) return;
        String js = "window.iFarmerLocationSuccess && window.iFarmerLocationSuccess("
                + location.getLatitude() + "," + location.getLongitude() + "," + location.getAccuracy() + ")";
        webView.post(() -> webView.evaluateJavascript(js, null));
    }

    private void sendLocationError(String reason) {
        if (webView == null) return;
        String safe = reason.replaceAll("[^a-z_]", "");
        webView.post(() -> webView.evaluateJavascript(
                "window.iFarmerLocationError && window.iFarmerLocationError('" + safe + "')", null));
    }

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

        FrameLayout root = new FrameLayout(this);
        root.addView(webView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(root);
        if (savedInstanceState == null) webView.loadUrl(HOME);
        else webView.restoreState(savedInstanceState);

        if (!hasLocationPermission()) {
            requestLocationPermission();
        } else {
            requestNotificationPermission();
        }
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
        if (hasLocationPermission() || locationPermissionRequestActive) return;
        locationPermissionRequestActive = true;
        requestPermissions(new String[] {
                Manifest.permission.ACCESS_FINE_LOCATION,
                Manifest.permission.ACCESS_COARSE_LOCATION
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
        if (requestCode == LOCATION_PERMISSION_REQUEST) {
            locationPermissionRequestActive = false;
            boolean granted = hasLocationPermission();
            if (pendingGeoCallback != null) {
                pendingGeoCallback.invoke(pendingGeoOrigin, granted, false);
                pendingGeoCallback = null;
                pendingGeoOrigin = null;
            }
            if (granted && pendingNativeCallback != null) {
                String cb = pendingNativeCallback; pendingNativeCallback = null;
                getCurrentLocation(cb);
            }
            if (!granted) {
                sendLocationError("permission");
                Toast.makeText(this, "iFarmer-এর লোকেশন চালু করতে Location permission দিন", Toast.LENGTH_LONG).show();
            }
            requestNotificationPermission();
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
        if (nativeLocationListener != null && locationManager != null) locationManager.removeUpdates(nativeLocationListener);
        if (webView != null) webView.destroy();
        super.onDestroy();
    }
}
