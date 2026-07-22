package com.github.fakegps;

/**
 * Created by tiger on 7/23/16.
 */
public interface IJoyStickPresenter {
    void onAnalogMove(float x, float y);
    void onSetLocationClick();

    void onFlyClick();

    void onBookmarkLocationClick();

    void onCopyLocationClick();

    void onArrowUpClick();

    void onArrowDownClick();

    void onArrowLeftClick();

    void onArrowRightClick();

}
