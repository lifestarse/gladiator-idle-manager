// Build: 1
package com.gladiator.ads;

/**
 * Single funnel for every async ad event crossing Java -> Python.
 *
 * Implemented on the Python side as a pyjnius PythonJavaClass. pyjnius can
 * only implement Java *interfaces* (java.lang.reflect.Proxy limitation),
 * which is the whole reason the AdsBridge shim exists: the GMA SDK delivers
 * loaded ads through abstract classes (InterstitialAdLoadCallback etc.)
 * that Python cannot subclass.
 *
 * Events (event / data):
 *   consent      ready | form_error:msg | update_error:msg
 *   init         complete
 *   banner       loaded | load_failed:code
 *   interstitial loaded | load_failed:code | dismissed | show_failed:msg
 *   rewarded     loaded | load_failed:code | earned:amount | dismissed
 *                | show_failed:msg
 */
public interface AdsCallback {
    void onAdEvent(String event, String data);
}
