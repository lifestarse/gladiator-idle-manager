// Build: 1
package com.gladiator.ads;

import android.app.Activity;
import android.util.DisplayMetrics;
import android.view.Gravity;
import android.view.View;
import android.widget.FrameLayout;

import com.google.android.gms.ads.AdError;
import com.google.android.gms.ads.AdListener;
import com.google.android.gms.ads.AdRequest;
import com.google.android.gms.ads.AdSize;
import com.google.android.gms.ads.AdView;
import com.google.android.gms.ads.FullScreenContentCallback;
import com.google.android.gms.ads.LoadAdError;
import com.google.android.gms.ads.MobileAds;
import com.google.android.gms.ads.interstitial.InterstitialAd;
import com.google.android.gms.ads.interstitial.InterstitialAdLoadCallback;
import com.google.android.gms.ads.rewarded.RewardItem;
import com.google.android.gms.ads.rewarded.RewardedAd;
import com.google.android.gms.ads.rewarded.RewardedAdLoadCallback;
import com.google.android.ump.ConsentInformation;
import com.google.android.ump.ConsentRequestParameters;
import com.google.android.ump.UserMessagingPlatform;

/**
 * Thin static bridge between Python (pyjnius) and the Google Mobile Ads SDK
 * (play-services-ads 24.x) plus the UMP consent SDK.
 *
 * Only callback adaptation and UI-thread hopping live here; the state
 * machine, reward gating and retry policy stay in Python (game/ads/).
 * All events are funneled through one AdsCallback (see its javadoc), always
 * invoked on the Android UI thread — the Python side re-schedules onto the
 * Kivy thread.
 *
 * Threading: the GMA SDK requires loading/showing ads on the main thread,
 * so every mutating entry point hops via Activity.runOnUiThread and Python
 * may call from the Kivy thread. Boolean getters read volatile fields only.
 */
public final class AdsBridge {

    private static volatile AdsCallback callback;
    private static volatile AdView banner;
    private static volatile boolean bannerLoaded;
    private static volatile InterstitialAd interstitial;
    private static volatile RewardedAd rewarded;

    private AdsBridge() {}

    private static void emit(String event, String data) {
        AdsCallback cb = callback;
        if (cb != null) {
            cb.onAdEvent(event, data);
        }
    }

    // --- Consent (UMP) ---

    public static void gatherConsent(final Activity activity, AdsCallback cb) {
        callback = cb;
        activity.runOnUiThread(() -> {
            ConsentRequestParameters params =
                    new ConsentRequestParameters.Builder().build();
            ConsentInformation info =
                    UserMessagingPlatform.getConsentInformation(activity);
            info.requestConsentInfoUpdate(
                    activity,
                    params,
                    () -> UserMessagingPlatform.loadAndShowConsentFormIfRequired(
                            activity,
                            formError -> emit("consent", formError == null
                                    ? "ready"
                                    : "form_error:" + formError.getMessage())),
                    updateError -> emit("consent",
                            "update_error:" + updateError.getMessage()));
        });
    }

    /** True when UMP allows ad requests (fresh or cached consent). */
    public static boolean canRequestAds(Activity activity) {
        return UserMessagingPlatform.getConsentInformation(activity)
                .canRequestAds();
    }

    // --- SDK init ---

    public static void initMobileAds(final Activity activity) {
        activity.runOnUiThread(() ->
                MobileAds.initialize(activity, status -> emit("init", "complete")));
    }

    // --- Banner (anchored adaptive, overlaid at the bottom of the screen) ---

    public static void loadBanner(final Activity activity, final String unitId) {
        activity.runOnUiThread(() -> {
            AdView existing = banner;
            if (existing != null) {
                existing.setVisibility(View.VISIBLE);
                if (!bannerLoaded) {
                    existing.loadAd(new AdRequest.Builder().build());
                }
                return;
            }
            AdView view = new AdView(activity);
            view.setAdUnitId(unitId);
            DisplayMetrics dm = new DisplayMetrics();
            activity.getWindowManager().getDefaultDisplay().getMetrics(dm);
            int widthDp = (int) (dm.widthPixels / dm.density);
            view.setAdSize(AdSize
                    .getCurrentOrientationAnchoredAdaptiveBannerAdSize(
                            activity, widthDp));
            view.setAdListener(new AdListener() {
                @Override
                public void onAdLoaded() {
                    bannerLoaded = true;
                    emit("banner", "loaded");
                }

                @Override
                public void onAdFailedToLoad(LoadAdError error) {
                    bannerLoaded = false;
                    emit("banner", "load_failed:" + error.getCode());
                }
            });
            FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.MATCH_PARENT,
                    FrameLayout.LayoutParams.WRAP_CONTENT,
                    Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
            activity.addContentView(view, lp);
            banner = view;
            view.loadAd(new AdRequest.Builder().build());
        });
    }

    public static void setBannerVisible(final Activity activity,
                                        final boolean visible) {
        activity.runOnUiThread(() -> {
            AdView view = banner;
            if (view != null) {
                view.setVisibility(visible ? View.VISIBLE : View.GONE);
            }
        });
    }

    // --- Interstitial ---

    public static void loadInterstitial(final Activity activity,
                                        final String unitId) {
        activity.runOnUiThread(() ->
                InterstitialAd.load(activity, unitId,
                        new AdRequest.Builder().build(),
                        new InterstitialAdLoadCallback() {
                            @Override
                            public void onAdLoaded(InterstitialAd ad) {
                                interstitial = ad;
                                emit("interstitial", "loaded");
                            }

                            @Override
                            public void onAdFailedToLoad(LoadAdError error) {
                                interstitial = null;
                                emit("interstitial",
                                        "load_failed:" + error.getCode());
                            }
                        }));
    }

    public static boolean isInterstitialLoaded() {
        return interstitial != null;
    }

    public static void showInterstitial(final Activity activity) {
        activity.runOnUiThread(() -> {
            InterstitialAd ad = interstitial;
            if (ad == null) {
                emit("interstitial", "show_failed:not_loaded");
                return;
            }
            interstitial = null; // one-shot object; never show twice
            ad.setFullScreenContentCallback(new FullScreenContentCallback() {
                @Override
                public void onAdDismissedFullScreenContent() {
                    emit("interstitial", "dismissed");
                }

                @Override
                public void onAdFailedToShowFullScreenContent(AdError error) {
                    emit("interstitial", "show_failed:" + error.getMessage());
                }
            });
            ad.show(activity);
        });
    }

    // --- Rewarded ---

    public static void loadRewarded(final Activity activity,
                                    final String unitId) {
        activity.runOnUiThread(() ->
                RewardedAd.load(activity, unitId,
                        new AdRequest.Builder().build(),
                        new RewardedAdLoadCallback() {
                            @Override
                            public void onAdLoaded(RewardedAd ad) {
                                rewarded = ad;
                                emit("rewarded", "loaded");
                            }

                            @Override
                            public void onAdFailedToLoad(LoadAdError error) {
                                rewarded = null;
                                emit("rewarded",
                                        "load_failed:" + error.getCode());
                            }
                        }));
    }

    public static boolean isRewardedLoaded() {
        return rewarded != null;
    }

    public static void showRewarded(final Activity activity) {
        activity.runOnUiThread(() -> {
            RewardedAd ad = rewarded;
            if (ad == null) {
                emit("rewarded", "show_failed:not_loaded");
                return;
            }
            rewarded = null; // one-shot object; never show twice
            ad.setFullScreenContentCallback(new FullScreenContentCallback() {
                @Override
                public void onAdDismissedFullScreenContent() {
                    emit("rewarded", "dismissed");
                }

                @Override
                public void onAdFailedToShowFullScreenContent(AdError error) {
                    emit("rewarded", "show_failed:" + error.getMessage());
                }
            });
            // "earned" fires only when the user actually watched through —
            // this is the only path that ever grants the in-game reward.
            ad.show(activity, (RewardItem item) ->
                    emit("rewarded", "earned:" + item.getAmount()));
        });
    }
}
