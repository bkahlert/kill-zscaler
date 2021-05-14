#!/bin/sh
/usr/bin/osascript -e 'do shell script "find /Library/LaunchDaemons -name *zscaler* -exec launchctl unload {} \\;" with administrator privileges'
/usr/bin/osascript -e 'do shell script "find /Library/LaunchAgents -name *zscaler* -exec launchctl unload {} \\;"'
