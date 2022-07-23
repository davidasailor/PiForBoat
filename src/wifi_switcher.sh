#!/bin/bash
# Tries to switch to a favored (higher bandwidth/lower cost) wifi network if available
# Checks for Internet connectivity and changes to an alternative wifi network if
# it detects a problem.
# Run by cron every few minutes

# Uncomment this pair and comment next for actual use
preferred_net="SSID_of_marina"
fallback_net="SSID_of_hotspot"

logfile=/var/log/wifi_switcher.log
echo "Date:" `date` >> $logfile

if /sbin/iwgetid | grep "$preferred_net" > /dev/null; then
    echo "Already on preferred net" >> $logfile
    
elif /usr/sbin/iw dev wlan0 scan | grep "$preferred_net" > /dev/null; then
    echo "Preferred net may be available; Will switch" >> $logfile
    preferred_id=`/usr/sbin/wpa_cli list_networks | grep "$preferred_net" | awk '{print $1}'`
    /usr/sbin/wpa_cli select_network $preferred_id
    sleep 10
    /usr/bin/wg-quick down wg0; sleep 3;  /usr/bin/wg-quick up wg0 

    else
        echo "Preferred net not available, staying on fallback net" >> $logfile
fi

echo "Checking connectivity..." >> $logfile

if ! ping -q -c 5 -W 1 192.168.5.1 > /dev/null; then
    if /sbin/iwgetid | grep "$fallback_net" > /dev/null; then
        echo "Fallback net has no connectivity; Will restart WG just in case" >> $logfile
        /usr/bin/wg-quick down wg0; sleep 3;  wg-quick up wg0
        echo "Restarted WG; If still no connectivity we are stuck" >> $logfile
    else
        echo "Preferred net has no network; falling back"
        fallback_id=`/usr/sbin/wpa_cli list_networks | grep "$fallback_net" | awk '{print $1}'`
        /usr/sbin/wpa_cli select_network $fallback_id
        /usr/bin/wg-quick down wg0; sleep 3; /usr/bin/wg-quick up wg0
    fi
else
    echo "Connectivity good" >> $logfile
fi

echo "END" >> $logfile

