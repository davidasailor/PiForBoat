#!/bin/bash
# Tries to switch to a favored (higher bandwidth/lower cost) wifi network if available
# Checks for Internet connectivity and changes to an alternative wifi network if
# it detects a problem.
# Run by cron every few minutes

logfile=/var/log/wifi_switcher.log
echo "Date:" `date` >> $logfile

# Locate config file (production path is /home/*/piForBoatPy.conf)
config_file=""
script_dir="$(dirname "$(readlink -f "$0")")"

# 1. Check local directory (for development)
if [ -f "$script_dir/piForBoatPy.conf" ]; then
    config_file="$script_dir/piForBoatPy.conf"
else
    # 2. Check all user home directories under /home/
    for h in /home/*; do
        if [ -f "$h/piForBoatPy.conf" ]; then
            config_file="$h/piForBoatPy.conf"
            break
        fi
    done
fi

# 3. Check /etc
if [ -z "$config_file" ] && [ -f "/etc/piForBoatPy.conf" ]; then
    config_file="/etc/piForBoatPy.conf"
fi

# 4. Fallback to current user's HOME, local example, or default path
if [ -z "$config_file" ]; then
    if [ -f "$script_dir/piForBoatPy.conf.example" ]; then
        config_file="$script_dir/piForBoatPy.conf.example"
    else
        user_home="${HOME:-/home/$(id -un)}"
        config_file="$user_home/piForBoatPy.conf"
    fi
fi

echo "Loading config from $config_file" >> $logfile

# Function to extract configuration values
get_config_val() {
    local key="$1"
    local file="$2"
    if [ -f "$file" ]; then
        grep -E "^[[:space:]]*${key}[[:space:]]*=" "$file" | tail -n 1 | cut -d'=' -f2- | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
    fi
}

# Function to manage docker compose stacks
manage_stack() {
    local stack_dir="$1"
    local action="$2" # "up -d" or "down"
    local log="$3"
    
    if [ -d "$stack_dir" ]; then
        local compose_file=""
        if [ -f "$stack_dir/docker-compose.yml" ]; then
            compose_file="$stack_dir/docker-compose.yml"
        elif [ -f "$stack_dir/docker-compose.yaml" ]; then
            compose_file="$stack_dir/docker-compose.yaml"
        fi
        
        if [ -n "$compose_file" ]; then
            echo "Executing 'docker compose $action' for stack in $stack_dir" >> "$log"
            if [ -x "$(command -v docker)" ] && docker compose version >/dev/null 2>&1; then
                docker compose -f "$compose_file" $action >> "$log" 2>&1
            elif [ -x "$(command -v docker-compose)" ]; then
                docker-compose -f "$compose_file" $action >> "$log" 2>&1
            else
                echo "Error: neither docker compose nor docker-compose found" >> "$log"
            fi
        else
            echo "Error: No docker-compose.yml or docker-compose.yaml found in $stack_dir" >> "$log"
        fi
    else
        echo "Dev environment: $stack_dir not found, skipping stack action: $action" >> "$log"
    fi
}

preferred_net=$(get_config_val "preferred_net" "$config_file")
fallback_net=$(get_config_val "fallback_net" "$config_file")

if [ -z "$preferred_net" ] || [ -z "$fallback_net" ]; then
    echo "Warning: preferred_net or fallback_net not found in config. Using defaults." >> $logfile
    preferred_net="${preferred_net:-SSID_of_marina}"
    fallback_net="${fallback_net:-SSID_of_hotspot}"
fi

echo "Preferred net: $preferred_net" >> $logfile
echo "Fallback net: $fallback_net" >> $logfile

if /sbin/iwgetid | grep "$preferred_net" > /dev/null; then
    echo "Already on preferred net" >> $logfile

else
    if /usr/bin/nmcli dev wifi | grep "$preferred_net" > /dev/null; then
        echo "Preferred net may be available; Will switch" >> $logfile
        /usr/bin/nmcli connection up "$preferred_net"
        sleep 2
        /usr/bin/wg-quick down wg0; sleep 3;  /usr/bin/wg-quick up wg0

    else
        echo "Preferred net not available, staying on fallback net" >> $logfile
    fi
fi

echo "Checking connectivity..." >> $logfile

if ! ping -q -c 5 -W 1 192.168.5.1 > /dev/null; then
    if /sbin/iwgetid | grep "$fallback_net" > /dev/null; then
        echo "Fallback net has no connectivity; Will restart WG just in case" >> $logfile
        /usr/bin/wg-quick down wg0; sleep 3;  wg-quick up wg0
        echo "Restarted WG; If still no connectivity we are stuck" >> $logfile
    else
        echo "Preferred net has no network; falling back"
        /usr/bin/nmcli connection up "$fallback_net"
        /usr/bin/wg-quick down wg0; sleep 3; /usr/bin/wg-quick up wg0
    fi
else
    echo "Connectivity good" >> $logfile
fi

echo "Checking Docker stacks status..." >> $logfile

# 1. Cloudflare stack status
if ping -q -c 3 -W 2 192.168.1.1 > /dev/null; then
    echo "WireGuard tunnel is UP (can ping 192.168.1.1). Bringing cloudflare stack down..." >> $logfile
    manage_stack "/docker/cloudflare" "down" "$logfile"
else
    if ping -q -c 3 -W 2 8.8.8.8 > /dev/null; then
        echo "WireGuard tunnel is BROKEN (can ping 8.8.8.8 but NOT 192.168.1.1). Starting cloudflare stack..." >> $logfile
        manage_stack "/docker/cloudflare" "up -d" "$logfile"
    else
        echo "No internet connectivity (cannot ping 8.8.8.8). Leaving cloudflare stack as is." >> $logfile
    fi
fi

# 2. Hawser stack status
if /sbin/iwgetid | grep "$preferred_net" > /dev/null; then
    echo "Connected to preferred network ($preferred_net). Starting hawser stack..." >> $logfile
    manage_stack "/docker/hawser" "up -d" "$logfile"
else
    echo "Not connected to preferred network ($preferred_net). Stopping hawser stack..." >> $logfile
    manage_stack "/docker/hawser" "down" "$logfile"
fi

echo "END" >> $logfile
