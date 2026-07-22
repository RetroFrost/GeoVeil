package com.github.fakegps.ui;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Bundle;
import android.text.TextUtils;
import android.view.ContextMenu;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.widget.AdapterView;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ListView;
import android.widget.Toast;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
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

public class FlyToActivity extends AppCompatActivity implements View.OnClickListener {
    private final double LAT_DEFAULT = 23.151637;
    private final double LON_DEFAULT = 113.344721;

    private final int FLY_TIME_DEFAULT = 60;

    public static final int DELETE_ID = 1001;

    private EditText mFromLocEditText;
    private EditText mLocEditText;
    private EditText mFlyTimeEditText;
    private ListView mListView;
    private Button mBtnStart;
    private BookmarkAdapter mAdapter;


    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_fly);

        // From location input
        mFromLocEditText = (EditText) findViewById(R.id.inputFromLoc);
        LocPoint currentLocPoint = JoyStickManager.get().getCurrentLocPoint();
        if (currentLocPoint != null) {
            mFromLocEditText.setText(currentLocPoint.toString());
        } else {
            String lastLocPoint = DbUtils.getLastLocPoint(this);
            if (!TextUtils.isEmpty(lastLocPoint)) {
                mFromLocEditText.setText(lastLocPoint);
            } else {
                mFromLocEditText.setText(new LocPoint(LAT_DEFAULT, LON_DEFAULT).toString());
            }
        }

        // To location input
        mLocEditText = (EditText) findViewById(R.id.inputLoc);
        mLocEditText.setHint("Latitude , Longitude");

        // Fly time input
        mFlyTimeEditText = (EditText) findViewById(R.id.inputFlyTime);
        mFlyTimeEditText.setText(String.valueOf(FLY_TIME_DEFAULT));

        mListView = (ListView) findViewById(R.id.list_bookmark);

        mBtnStart = (Button) findViewById(R.id.btn_fly);
        mBtnStart.setOnClickListener(this);
        updateBtn();

        initListView();

        registerBroadcastReceiver();
    }

    @Override
    public void onClick(View view) {
        int flyTime = FakeGpsUtils.getIntValueFromInput(this, mFlyTimeEditText);
        LocPoint fromPoint = FakeGpsUtils.getLocPointFromInput(this, mFromLocEditText);
        LocPoint toPoint = FakeGpsUtils.getLocPointFromInput(this, mLocEditText);

        int id = view.getId();
        if (id == R.id.btn_fly) {
            if (JoyStickManager.get().isStarted()) {
                if (JoyStickManager.get().isFlyMode()) {
                    JoyStickManager.get().stopFlyMode();
                } else {
                    if (fromPoint != null && toPoint != null && flyTime > 0) {
                        // Jump to the "From" location first, then fly to "To"
                        JoyStickManager.get().jumpToLocation(fromPoint);
                        JoyStickManager.get().flyToLocation(toPoint, flyTime);
                    } else {
                        Toast.makeText(this, "Input is not valid!", Toast.LENGTH_SHORT).show();
                    }
                }
            }
            updateBtn();
        }
    }

    private void updateBtn() {
        if (JoyStickManager.get().isFlyMode()) {
            mBtnStart.setText(R.string.btn_fly_stop);
        } else {
            mBtnStart.setText(R.string.btn_fly_start);
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
                        ArrayList<LocBookmark> allBookmark = DbUtils.getAllBookmark();
                        mAdapter.setLocBookmarkList(allBookmark);
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
    protected void onDestroy() {
        unregisterBroadcastReceiver();
        super.onDestroy();
    }

    public static void startPage(Context context) {
        Intent intent = new Intent(context, FlyToActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        context.startActivity(intent);
    }


}
