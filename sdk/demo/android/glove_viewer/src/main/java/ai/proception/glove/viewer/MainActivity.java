package ai.proception.glove.viewer;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

import ai.proception.proglove.GloveChannel;
import ai.proception.proglove.GloveProtoSession;
import ai.proception.proglove.GloveSide;
import ai.proception.proglove.UsbGloveTransport;

import java.util.Locale;

/**
 * Plug a Proception Glove into this device and watch it stream.
 *
 * Connects to the first glove it finds, drives the stream, and shows the
 * taxels, the IMU quaternion and the frame rate. Two views: the taxels laid
 * out on the hand, and a plain grid.
 *
 * Everything here is SDK API — this file is the worked example. Log tag:
 * ProGloveSdk.
 */
public final class MainActivity extends Activity implements GloveChannel.Listener {

    private static final String TAG = "ProGloveSdk";

    /** Which glove this sample opens. Drives the session, the channel and the hand layout. */
    private static final GloveSide SIDE = GloveSide.LEFT;
    private static final long POLL_INTERVAL_MS = 16;
    private static final long RECONNECT_INTERVAL_MS = 1000;

    /** Cadence of the one-line status the deployment test reads back over logcat. */
    private static final long REPORT_INTERVAL_MS = 2000;

    private final Handler handler = new Handler(Looper.getMainLooper());

    private UsbGloveTransport transport;
    private GloveChannel channel;
    private TextView statusText;
    private TextView deviceText;
    private TextView imuText;
    private TaxelGridView grid;
    private GloveHandView hand;
    private Button filterButton;
    private Button viewButton;

    private boolean filterEnabled = true;
    private boolean handView = true;
    private long lastOpenAttemptMs;
    private long lastReportMs;
    private int lastReportedStatus = -1;
    private int[] latestTaxels;
    private int latestUid;
    private float[] latestQuat;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // A sleeping screen pauses the activity, which stops the poll loop and
        // with it the heartbeat the glove needs — the stream would die while
        // someone watches the device do nothing.
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        setContentView(buildUi());

        transport = new UsbGloveTransport(this);
        channel = new GloveChannel(SIDE, transport);
        hand.setPositions(GloveProtoSession.taxelPositionsMm(SIDE));
    }

    @Override
    protected void onResume() {
        super.onResume();
        handler.post(tick);
    }

    @Override
    protected void onPause() {
        super.onPause();
        handler.removeCallbacks(tick);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        channel.close();
    }

    @Override
    public void onTactile(int[] taxels, int uid, int timestampMs) {
        latestTaxels = taxels;
        latestUid = uid;
    }

    @Override
    public void onImu(float[] quat, int timestampMs) {
        latestQuat = quat;
    }

    private final Runnable tick = new Runnable() {
        @Override
        public void run() {
            long now = SystemClock.elapsedRealtime();

            // open() is cheap when the port is already up, and it is how the
            // permission dialog gets re-posted after a denial or a replug.
            if (!transport.isOpen() && now - lastOpenAttemptMs > RECONNECT_INTERVAL_MS) {
                lastOpenAttemptMs = now;
                channel.open(0);
            }

            channel.poll(MainActivity.this);
            render();
            report(now);
            handler.postDelayed(this, POLL_INTERVAL_MS);
        }
    };

    /**
     * One status line per state change, plus a heartbeat with the numbers.
     * `adb logcat -s ProGloveSdk` is the whole diagnostic surface.
     */
    private void report(long now) {
        int status = transport.status();
        boolean changed = status != lastReportedStatus;
        if (!changed && now - lastReportMs < REPORT_INTERVAL_MS) {
            return;
        }
        lastReportedStatus = status;
        lastReportMs = now;
        Log.i(TAG, String.format(
                Locale.US,
                "status=%s devices=%d handedness=%s frames=%d hz=%.1f peak=%d error=%s",
                statusLabel(status).replace(' ', '_'),
                transport.listDevices().length,
                channel.handednessConfirmed() ? (channel.handednessMismatch() ? "mismatch" : "ok") : "unknown",
                channel.frameCount(),
                channel.hz(),
                peakTaxel(),
                transport.lastError().isEmpty() ? "none" : transport.lastError().replace(' ', '_')));
    }

    private int peakTaxel() {
        if (latestTaxels == null) {
            return 0;
        }
        int peak = 0;
        for (int value : latestTaxels) {
            peak = Math.max(peak, value);
        }
        return peak;
    }

    private void render() {
        statusText.setText(String.format(
                Locale.US,
                "%s · %s · %d frames · %.0f Hz · peak %d",
                statusLabel(transport.status()),
                handednessLabel(),
                channel.frameCount(),
                channel.hz(),
                peakTaxel()));

        String[] devices = transport.listDevices();
        String serial = transport.openedSerialNumber();
        StringBuilder devicesLabel = new StringBuilder();
        if (devices.length == 0) {
            devicesLabel.append("no glove attached");
        }
        for (String device : devices) {
            devicesLabel.append(device).append('\n');
        }
        if (!serial.isEmpty()) {
            devicesLabel.append("open: SN=").append(serial);
        }
        String error = transport.lastError();
        if (!error.isEmpty()) {
            devicesLabel.append("\nlast error: ").append(error);
        }
        deviceText.setText(devicesLabel.toString().trim());

        if (latestTaxels != null) {
            grid.setValues(latestTaxels);
            hand.setValues(latestTaxels);
        }
        if (latestQuat != null) {
            imuText.setText(String.format(
                    Locale.US,
                    "uid %d · quat w %.3f  x %.3f  y %.3f  z %.3f",
                    latestUid,
                    latestQuat[0],
                    latestQuat[1],
                    latestQuat[2],
                    latestQuat[3]));
        }
    }

    private String statusLabel(int status) {
        switch (status) {
            case UsbGloveTransport.STATUS_CONNECTED:
                return "connected";
            case UsbGloveTransport.STATUS_CONNECTING:
                return "connecting";
            case UsbGloveTransport.STATUS_PERMISSION_REQUIRED:
                return "waiting for USB permission";
            case UsbGloveTransport.STATUS_ERROR:
                return "error";
            default:
                return "disconnected";
        }
    }

    private String handednessLabel() {
        if (!channel.handednessConfirmed()) {
            return "side unknown";
        }
        return channel.handednessMismatch() ? "RIGHT glove on a LEFT session" : "side confirmed";
    }

    private View buildUi() {
        // The outer view takes the system insets — without it the status bar and
        // the navigation bar sit on top of the first and last line — and the
        // inner one owns the margin, since fitsSystemWindows overwrites padding.
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.BLACK);
        root.setFitsSystemWindows(true);

        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(24, 16, 24, 16);
        root.addView(content, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        statusText = label(content, "starting");
        deviceText = label(content, "");

        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.HORIZONTAL);
        buttons.setGravity(Gravity.CENTER);
        content.addView(buttons);

        button(buttons, "Perm", v -> transport.requestPermissionForAll());
        button(buttons, "Zero", v -> channel.session().snapshotBaseline());
        filterButton = button(buttons, "Filt on", v -> toggleFilter());
        viewButton = button(buttons, "Hand", v -> toggleView());

        // Both views are built once and swapped by visibility: the hand layout
        // costs a neighbour-distance pass to size its dots, and a press should
        // not stutter because someone tapped the toggle.
        FrameLayout canvas = new FrameLayout(this);
        hand = new GloveHandView(this);
        grid = new TaxelGridView(this);
        grid.setVisibility(View.GONE);
        canvas.addView(hand);
        canvas.addView(grid);
        content.addView(canvas, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        imuText = label(content, "no IMU frame yet");
        return root;
    }

    private void toggleView() {
        handView = !handView;
        hand.setVisibility(handView ? View.VISIBLE : View.GONE);
        grid.setVisibility(handView ? View.GONE : View.VISIBLE);
        viewButton.setText(handView ? "Hand" : "Grid");
    }

    private void toggleFilter() {
        filterEnabled = !filterEnabled;
        channel.session().setFilterEnabled(filterEnabled);
        filterButton.setText(filterEnabled ? "Filt on" : "Filt off");
    }

    private TextView label(ViewGroup parent, String text) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextColor(Color.WHITE);
        view.setTextSize(14f);
        parent.addView(view);
        return view;
    }

    private Button button(ViewGroup parent, String text, View.OnClickListener listener) {
        Button view = new Button(this);
        view.setText(text);
        view.setTextSize(12f);
        view.setOnClickListener(listener);
        parent.addView(view, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        return view;
    }
}
