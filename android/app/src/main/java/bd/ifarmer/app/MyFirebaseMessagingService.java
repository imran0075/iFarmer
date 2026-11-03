package bd.ifarmer.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Intent;
import android.os.Build;

import androidx.core.app.NotificationCompat;

import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;

public class MyFirebaseMessagingService extends FirebaseMessagingService {
    private static final String CHANNEL_ID = "ifarmer_updates";

    @Override
    public void onMessageReceived(RemoteMessage message) {
        String title = message.getNotification() != null
                ? message.getNotification().getTitle() : message.getData().get("title");
        String body = message.getNotification() != null
                ? message.getNotification().getBody() : message.getData().get("body");
        if (title == null || title.trim().isEmpty()) title = "iFarmer";
        if (body == null || body.trim().isEmpty()) body = "আপনার জন্য নতুন বিজ্ঞপ্তি এসেছে।";
        showNotification(title, body);
    }

    private void showNotification(String title, String body) {
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (manager == null) return;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID, "iFarmer বিজ্ঞপ্তি", NotificationManager.IMPORTANCE_DEFAULT);
            channel.setDescription("iFarmer কৃষি তথ্য ও সতর্কবার্তা");
            manager.createNotificationChannel(channel);
        }
        Intent open = new Intent(this, MainActivity.class);
        open.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pending = PendingIntent.getActivity(this, 0, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification notification = new NotificationCompat.Builder(this, CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_ifarmer)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(body))
                .setContentIntent(pending)
                .setAutoCancel(true)
                .build();
        manager.notify((int) System.currentTimeMillis(), notification);
    }
}