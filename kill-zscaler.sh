#!/bin/sh
find /Library/LaunchAgents -name '*zscaler*' -exec launchctl unload {} \;
sudo find /Library/LaunchDaemons -name '*zscaler*' -exec launchctl unload {} \;
