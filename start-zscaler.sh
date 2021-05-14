#!/bin/sh
open -a /Applications/Zscaler/Zscaler.app --hide
sudo find /Library/LaunchDaemons -name '*zscaler*' -exec launchctl load {} \;
