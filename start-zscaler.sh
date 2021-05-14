#!/bin/sh
open -a /Applications/ZScaler/ZScaler.app --hide
sudo find /Library/LaunchDaemons -name '*zscaler*' -exec launchctl load {} \;
