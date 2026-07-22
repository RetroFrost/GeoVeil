package com.github.fakegps.ui;

import android.Manifest;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.IntentFilter;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.text.TextUtils;
import android.view.ContextMenu;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.view.MenuInflater;
import android.widget.AdapterView;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.ListView;
import android.widget.Toast;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.localbroadcastmanager.content.LocalBroadcastManager;

import com.github.fakegps.BroadcastEvent;
import com.github.fakegps.DbUtils;
import com.github.fakegps.FakeGpsApp;
import com.github.fakegps.FakeGpsUtils;
import com.github.fakegps.JoyStickManager;
import com.github.fakegps.model.LocBookmark;
import com.github.fakegps.model.LocPoint;
import com.tencent.fakegps.R;

import java.util.ArrayList;

public class MainActivity extends AppCompatActivity implements View.OnClickListener {
    private final double LAT_DEFAULT = 37.802406;
    private final double LON_DEFAULT = -122.401779;

    private static final int REQUEST_CODE_OVERLAY = 2001;
    private static final int REQUEST_CODE_LOCATION = 2002;
    private static final int REQUEST_CODE_NOTIFICATION = 2003;

    public static final int DELETE_ID = 1001;

    private EditText mLocEditText;
    private EditText mMoveStepEditText;
    private ListView mListView;
    private Button mBtnStart;
    private Button mBtnSetNew;
    private Button mBtnRestoreAnalog;
    private CheckBox mAutoShowAnalog;
    private BookmarkAdapter mAdapter;

    // Pending start params - saved while requesting permissions
    private LocPoint mPendingStartPoint;
    private double mPendingStartStep;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        //location input
        mLocEditText = (EditText) findViewById(R.id.inputLoc);
        LocPoint currentLocPoint = JoyStickManager.get().getCurrentLocPoint();
        if (currentLocPoint != null) {
            mLocEditText.setText(currentLocPoint.toString());
        } else {
            String lastLocPoint = DbUtils.getLastLocPoint(this);
            if (!TextUtils.isEmpty(lastLocPoint)) {
                mLocEditText.setText(lastLocPoint);
            } else {
                mLocEditText.setText(new LocPoint(LAT_DEFAULT, LON_DEFAULT).toString());
            }
        }

        mLocEditText.setSelection(mLocEditText.getText().length());

        //each move step delta
        mMoveStepEditText = (EditText) findViewById(R.id.inputStep);
        double currentMoveStep = JoyStickManager.get().getMoveStep();
        mMoveStepEditText.setText(String.valueOf(currentMoveStep));

        mListView = (ListView) findViewById(R.id.list_bookmark);

        mBtnStart = (Button) findViewById(R.id.btn_start);
        mBtnStart.setOnClickListener(this);
        updateBtnStart();

        mBtnSetNew = (Button) findViewById(R.id.btn_set_loc);
        mBtnSetNew.setOnClickListener(this);
        updateBtnSetNew();

        mAutoShowAnalog = findViewById(R.id.checkbox_auto_show_analog);
        mAutoShowAnalog.setChecked(JoyStickManager.get().isAutoShowEnabled());
        mAutoShowAnalog.setOnCheckedChangeListener((button, checked) ->
                JoyStickManager.get().setAutoShowEnabled(checked));

        mBtnRestoreAnalog = findViewById(R.id.btn_restore_analog);
        mBtnRestoreAnalog.setOnClickListener(v -> JoyStickManager.get().restoreJoyStick());

        initListView();

        registerBroadcastReceiver();
    }

    @Override
    public void onClick(View view) {
        double step = FakeGpsUtils.getMoveStepFromInput(this, mMoveStepEditText);
        LocPoint point = FakeGpsUtils.getLocPointFromInput(this, mLocEditText);

        int id = view.getId();
        if (id == R.id.btn_start) {
            if (!JoyStickManager.get().isStarted()) {
                if (point == null) {
                    Toast.makeText(this, "Input is not valid!", Toast.LENGTH_SHORT).show();
                    return;
                }
                // Save pending params and start permission check chain
                mPendingStartPoint = point;
                mPendingStartStep = step;
                checkPermissionsAndStart();
            } else {
                LocPoint currentLocPoint = JoyStickManager.get().getCurrentLocPoint();
                if (currentLocPoint != null) {
                    DbUtils.saveLastLocPoint(this, currentLocPoint);
                }
                JoyStickManager.get().stop();
                finish();
            }
            updateBtnStart();
            updateBtnSetNew();
        } else if (id == R.id.btn_set_loc) {
            if (step > 0 && point != null) {
                JoyStickManager.get().setMoveStep(step);
                JoyStickManager.get().jumpToLocation(point);
            } else {
                Toast.makeText(this, "Input is not valid!", Toast.LENGTH_SHORT).show();
            }
        }
    }

    /**
     * Checks all required permissions in order:
     * 1. Location permission (required for foreground service with location type)
     * 2. Notification permission (Android 13+)
     * 3. Overlay permission (for floating joystick)
     * Then starts the service if all granted.
     */
    private void checkPermissionsAndStart() {
        // Step 1: Check location permission
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this,
                    new String[]{Manifest.permission.ACCESS_FINE_LOCATION},
                    REQUEST_CODE_LOCATION);
            return;
        }

        // Step 2: Check notification permission (Android 13+)
        if (Build.VERSION.SDK_INT >= 33) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                    != PackageManager.PERMISSION_GRANTED) {
                ActivityCompat.requestPermissions(this,
                        new String[]{Manifest.permission.POST_NOTIFICATIONS},
                        REQUEST_CODE_NOTIFICATION);
                return;
            }
        }

        // Step 3: Check overlay permission
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            if (!Settings.canDrawOverlays(this)) {
                new AlertDialog.Builder(this)
                        .setTitle("Overlay permission required")
                        .setMessage("GeoAvil needs overlay permission to display the floating joystick. Because this APK was installed outside an app store, first open GeoAvil's App Info and choose ⋮ > Allow restricted settings. Then enable Display over other apps.")
                        .setPositiveButton("Open app info", new DialogInterface.OnClickListener() {
                            @Override
                            public void onClick(DialogInterface dialog, int which) {
                                Intent intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                        Uri.parse("package:" + getPackageName()));
                                startActivityForResult(intent, REQUEST_CODE_OVERLAY);
                            }
                        })
                        .setNegativeButton("Cancel", null)
                        .show();
                return;
            }
        }

        // All permissions granted, start!
        doStart();
    }

    private void doStart() {
        if (mPendingStartPoint != null) {
            JoyStickManager.get().setMoveStep(mPendingStartStep);
            JoyStickManager.get().start(mPendingStartPoint);
            mPendingStartPoint = null;
            finish();
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_CODE_LOCATION) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                // Location granted, continue checking next permission
                checkPermissionsAndStart();
            } else {
                Toast.makeText(this, "Location permission is required to simulate GPS.", Toast.LENGTH_LONG).show();
            }
        } else if (requestCode == REQUEST_CODE_NOTIFICATION) {
            // Notification permission is optional, continue regardless
            checkPermissionsAndStart();
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_CODE_OVERLAY) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && Settings.canDrawOverlays(this)) {
                // Overlay granted, continue the chain
                checkPermissionsAndStart();
            } else {
                Toast.makeText(this, "Overlay permission was not granted.", Toast.LENGTH_SHORT).show();
            }
        }
    }

    private void updateBtnStart() {
        if (JoyStickManager.get().isStarted()) {
            mBtnStart.setText(R.string.btn_stop);
        } else {
            mBtnStart.setText(R.string.btn_start);
        }
    }

    private void updateBtnSetNew() {
        if (JoyStickManager.get().isStarted()) {
            mBtnSetNew.setEnabled(true);
        } else {
            mBtnSetNew.setEnabled(false);
        }
    }

    private void initListView() {
        mAdapter = new BookmarkAdapter(this);
        ArrayList<LocBookmark> allBookmark = DbUtils.getAllBookmark();
        mAdapter.setLocBookmarkList(allBookmark);
        mListView.setAdapter(mAdapter);

        View emptyView = findViewById(R.id.empty_view);
        mListView.setEmptyView(emptyView);

        mListView.setOnItemClickListener(new AdapterView.OnItemClickListener() {
            @Override
            public void onItemClick(AdapterView<?> parent, View view, int position, long id) {
                LocPoint locPoint = mAdapter.getItem(position).getLocPoint();
                mLocEditText.setText(locPoint != null ? locPoint.toString() : "");
            }
        });

        registerForContextMenu(mListView);

    }

    @Override
    public void onCreateContextMenu(ContextMenu menu, View v, ContextMenu.ContextMenuInfo menuInfo) {
        menu.add(Menu.NONE, DELETE_ID, Menu.NONE, R.string.menu_delete);
        super.onCreateContextMenu(menu, v, menuInfo);
    }

    public boolean onContextItemSelected(MenuItem item) {
        if (item.getItemId() == DELETE_ID) {
            AdapterView.AdapterContextMenuInfo info = (AdapterView.AdapterContextMenuInfo) item.getMenuInfo();
            delete(info.position);
            return true;
        }
        return super.onContextItemSelected(item);
    }

    private void delete(final int position) {
        if (position < 0) return;
        final LocBookmark bookmark = mAdapter.getItem(position);
        new AlertDialog.Builder(this)
                .setTitle("Delete " + bookmark.toString())
                .setPositiveButton("OK", new DialogInterface.OnClickListener() {
                    public void onClick(DialogInterface dialog, int which) {
                        DbUtils.deleteBookmark(bookmark);
                    }
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    private void registerBroadcastReceiver() {
        IntentFilter intentFilter = new IntentFilter(BroadcastEvent.BookMark.ACTION_BOOK_MARK_UPDATE);
        LocalBroadcastManager.getInstance(FakeGpsApp.get()).registerReceiver(mBroadcastReceiver, intentFilter);
    }

    private void unregisterBroadcastReceiver() {
        LocalBroadcastManager.getInstance(FakeGpsApp.get()).unregisterReceiver(mBroadcastReceiver);
    }

    private BroadcastReceiver mBroadcastReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            String action = intent.getAction();
            if (BroadcastEvent.BookMark.ACTION_BOOK_MARK_UPDATE.equals(action)) {
                ArrayList<LocBookmark> allBookmark = DbUtils.getAllBookmark();
                mAdapter.setLocBookmarkList(allBookmark);
            }
        }
    };

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        getMenuInflater().inflate(R.menu.main_menu, menu);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == R.id.menu_mock_status) {
            showMockStatusTester();
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    private void showMockStatusTester() {
        final TextView status = new TextView(this);
        status.setPadding(48, 32, 48, 16);
        status.setText("Waiting for a location update…");
        final AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle("Mock location status")
                .setView(status)
                .setNegativeButton("Close", null)
                .create();

        final LocationManager locationManager = (LocationManager) getSystemService(LOCATION_SERVICE);
        final LocationListener listener = new LocationListener() {
            @Override
            public void onLocationChanged(@NonNull Location location) {
                String provider = location.getProvider() == null ? "unknown" : location.getProvider();
                status.setText(String.format(java.util.Locale.US,
                        "isMock = %s\n\nProvider: %s\nLatitude: %.6f\nLongitude: %.6f\nAccuracy: %.1f m",
                        location.isMock() ? "true" : "false", provider,
                        location.getLatitude(), location.getLongitude(), location.getAccuracy()));
            }
        };
        dialog.setOnShowListener(ignored -> {
            try {
                if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                        != PackageManager.PERMISSION_GRANTED) {
                    status.setText("Location permission is required to test isMock.");
                    return;
                }
                locationManager.requestLocationUpdates(LocationManager.GPS_PROVIDER, 1000, 0, listener);
                locationManager.requestLocationUpdates(LocationManager.NETWORK_PROVIDER, 1000, 0, listener);
                Location last = locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER);
                if (last != null) listener.onLocationChanged(last);
            } catch (Exception e) {
                status.setText("Unable to read location: " + e.getMessage());
            }
        });
        dialog.setOnDismissListener(ignored -> locationManager.removeUpdates(listener));
        dialog.show();
    }


    @Override
    protected void onDestroy() {
        unregisterBroadcastReceiver();
        super.onDestroy();
    }

    public static void startPage(Context context) {
        Intent intent = new Intent(context, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP);
        context.startActivity(intent);
    }


}
