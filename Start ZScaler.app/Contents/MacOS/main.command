#!/bin/sh
/usr/bin/osascript -e 'do shell script "open -a /Applications/ZScaler/ZScaler.app --hide"'
/usr/bin/osascript -e 'do shell script "find /Library/LaunchDaemons -name *zscaler* -exec launchctl load {} \\;" with administrator privileges'
