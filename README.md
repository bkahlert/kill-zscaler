*Instructions on [how to share the connection of a Zscaler installed in a virtual machine](#sharing-zscaler) can be found below.*

# Killing Zscaler on macOS

Zscaler can be annoying if you're trying to stop it. Despite having administrative rights, usually it asks for a password.

Pick one of the following options to take back control.

## Using the App

People who prefer to use apps over command lines, can use
`Kill Zscaler.app` which is a simple wrapper of the shell script described below.

- [Download this repository as an archive](https://github.com/bkahlert/kill-zscaler/archive/refs/heads/main.zip).
- Open `Kill Zscaler.app` to kill Zscaler.
- To use Zscaler again, reboot or open `Start Zscaler.app`.

![Kill Zscaler and Start Zscaler app](apps.png)

## Using a Shell Script

- Open Terminal or whatever terminal you prefer (e.g. [iTerm2](https://iterm2.com/)).
- Type `git clone https://github.com/bkahlert/kill-zscaler.git`
- Type `cd kill-zscaler` to change into the newly cloned repository.
- Make sure the scripts are executable by running `chmod +x kill-zscaler.sh start-zscaler.sh`
- Type `./kill-zscaler.sh` to kill Zscaler.
- To use Zscaler again, reboot or type `./start-zscaler.sh`.

## Using a Shell

- Open Terminal or whatever terminal you prefer (e.g. [iTerm2](https://iterm2.com/)).
- Type `find /Library/LaunchAgents -name '*zscaler*' -exec launchctl unload {} \;;sudo find /Library/LaunchDaemons -name '*zscaler*' -exec launchctl unload {} \;`
to kill Zscaler.
- To use Zscaler again, reboot or
  type `open -a /Applications/Zscaler/Zscaler.app --hide; sudo find /Library/LaunchDaemons -name '*zscaler*' -exec launchctl load {} \;`.

### Using an Alias

To kill Zscaler by typing `kill-zscaler` (and to start it with `start-zscaler`) do the following steps:

- Open the shell initialization file of your shell
  - Bash: ~/.bashrc
  - ZSH: ~/.zshrc
  - For more information aliases, read https://medium.com/@rajsek/zsh-bash-startup-files-loading-order-bashrc-zshrc-etc-e30045652f2e or any other appropriate Google
    match.
- Add the contents of `kill-zscaler.alias.txt` or the following lines to it:
  ```shell
  alias start-zscaler="open -a /Applications/Zscaler/Zscaler.app --hide; sudo find /Library/LaunchDaemons -name '*zscaler*' -exec launchctl load {} \;"
  alias kill-zscaler="find /Library/LaunchAgents -name '*zscaler*' -exec launchctl unload {} \;;sudo find /Library/LaunchDaemons -name '*zscaler*' -exec launchctl unload {} \;"
  ```
- Open a new shell (or type `source ~/.bashrc` / `source ~/.zshrc` / … to load your changes)
- Type `kill-zscaler` to kill Zscaler
- To use Zscaler again, reboot or type `start-zscaler`.


# Sharing Zscaler

To share an existing Zscaler VPN tunnel you can use [share-zscaler.v2.sh](share-zscaler.v2.sh) on the machine
with Zscaler installed as follows:
```shell
./share-zscaler.sh \
  --probe foo.bar.internal \
  --domain internal
```

- The script sets up network address translation (NAT) on the VPN client machine
  so that its VPN tunnel can be shared.
  - The `--prope` argument can be any hostname you want to connect to using the VPN tunnel.
    It's used to determine the connection details of your VPN connection.
  - The domains specified with one or more `--domain` arguments are used to
    customize the DNS name resolution on your host.
    This makes your host use your VPN client's name resolution for the specified domains (and sub-domains).
- It prints a configuration script that needs to be run on your host to make it use the just shared tunnel. 

If you prefer to have a one-liner without having to download anything you can use the following
command *at your own risk*:

```shell
bash -c "$(curl -so- https://raw.githubusercontent.com/bkahlert/kill-zscaler/main/share-zscaler.v2.sh)" -- \
  --probe foo.bar.internal \
  --domain internal
```

## Parallels macOS VM

If you only have a macOS client at hand you can set up a virtual macOS machine using [Parallels](https://www.parallels.com/pd/virtual-machines-for-mac).

1. [Install Parallels](https://www.parallels.com/products/desktop/trial/)
2. Set up a virtual machine
   1. The following scripts sets up a macOS machine with minimal footprint:
      ```shell
      declare -r PARALLELS=/Applications/Parallels\ Desktop.app
      declare -r VMDIR=$HOME/Parallels
      declare -r NAME=Zscaler
      curl -LfSo "$VMDIR/macOS.ipsw" "$("$PARALLELS"/Contents/MacOS/prl_macvm_create --getipswurl)"
      "$PARALLELS"/Contents/MacOS/prl_macvm_create "$VMDIR/macOS.ipsw" "$VMDIR/$NAME.macvm" --disksize 40000000000
      cat <<CONFIG >"$VMDIR/$NAME.macvm/config.ini"
      [Hardware]
      vCPU.Count=1
      Memory.Size=2147483648
      Display.Width=1920
      Display.Height=1080
      Display.DPI=96
      Sound.Enabled=0
      Network.Type=1
      CONFIG
      open "$VMDIR"
      open -a "$PARALLELS" "$VMDIR/$NAME.macvm"
      ```
      Take the chance to customize the above settings to your requirements.   
      **At the time of writing, the disk size cannot be altered later.**  
      40GB disk space (see `--disksize` argument) are recommended.  
      32GB disk space are the bare minimum.  
   3. Create a macOS user
   4. Install Parallels Tools and reboot
   5. Install Zscaler
   6. Login
3. Establish connection
   1. Start Zscaler (if not already running)
   2. [Run share-zscaler.sh](#sharing-zscaler)
4. Use connection
   1. On your local machine open a terminal
   2. Paste the host configuration script (that was printed in the previous step) in the terminal and run it

**You can now connect to all hosts you listed in step 2** 🎉

Optionally, you can set the name of your VM in
1. System Preferences → Network → Ethernet → Advanced... → WINS → NetBIOS Name
2. System Preferences → Sharing → Computer Name

## Remote Execution

This section describes the necessary steps to run `share-zscaler.v2.sh` on your
local machine instead of the virtual Zscaler machine using SSH.

### Preparation

#### On your virtual machine
1. Activate SSH by checking System Preferences → Sharing → Remote Login
2. Optionally extend your sudoers so that you may run `sysctl` and `pfctl` without having to enter your password:
   ```shell
   (
   echo "$(whoami) ALL=NOPASSWD: /usr/sbin/sysctl *"
   echo "$(whoami) ALL=NOPASSWD: /sbin/pfctl *"
   ) | sudo tee /etc/sudoers.d/zscaler
   ```
3. Optionally prepare a script with the following contents to lock your screen
   ```bash
   cat << 'LOCK_SCREEN' > ~/Desktop/lock-screen
   #!/bin/bash
   osascript -e 'tell application "System Events" to keystroke "q" using {command down,control down}'
   LOCK_SCREEN
   chmod +x ~/Desktop/lock-screen
   ```
   and run it on login via System Preferences → *Choose your user* → Login items → + → *Select your lock screen script*  
   Don't forget to make it executable using `chmod +x` and to run it once to provide it with sufficient permissions.
4. If the IP of your VPN client machine is dynamic and you can't reliably resolve its IP, a workaround can be to install [GeekTool](https://www.tynsoe.org/geektool/) and display the output of `ipconfig getifaddr en0` in a script Geeklet. At least you now find out the current IP easily.

#### On your local machine

1. [Create an SSH key](https://www.google.com/search?q=create+ssh+key+macos) or use an existing one
2. Copy the public key of your just created key pair to your Zscaler machine:
   ```shell
   ssh-copy-id -i ~/.ssh/id_rsa zscaler@Zscaler.local
   ```
   *This snippet assumes that your Zscaler host has the name `Zscaler` and your user account on that machine is `zscaler`.*
3. Check if you can log in:
   ```shell
   ssh zscaler@Zscaler.local printenv
   ```
   If the output shows the environment variables of your Zscaler host, all is fine.

### Execution

The following command needs to be run on your working machine,
which then connects to the host `Zscaler` with user `zscaler`,
and finishes configuring your working machine using the returned configuration Bash script:
```shell
(
  bash <<'SHARE_ZSCALER_V2'
ssh -4t zscaler@Zscaler.local '
bash -c "$(curl -so- https://raw.githubusercontent.com/bkahlert/kill-zscaler/main/share-zscaler.v2.sh)" -- \
  --probe foo.bar.internal \
  --domain internal
'
SHARE_ZSCALER_V2
) | bash
```

You get prompted for the password of user `zscaler` (unless you did the optional [sudoers configuration](#on-your-virtual-machine)).

> 💡 Users with a VPN host machine with dynamic IP can try to
change the `ssh` command to:
> ```shell
> ssh -4t "zscaler@$(sudo nmap -n -p 22 192.168.206.2-254 -oG - | awk '/Up$/{print $2}')"
> ```
> Be sure to change the `192.168.206` part to match the client's address range.
> The above `nmap` command looks for a machine with an open SSH port and pass the match to the `ssh` command. 

**Example output**:
```
No ALTQ support in kernel
ALTQ related functions disabled
pfctl: pf not enabled
No ALTQ support in kernel
ALTQ related functions disabled
rules cleared
nat cleared
dummynet cleared
0 tables deleted.
0 states cleared
source tracking entries cleared
pf: statistics cleared
pf: interface flags reset
pfctl: Use of -f option, could result in flushing of rules
present in the main ruleset added by the system at startup.
See /etc/pf.conf for further details.

No ALTQ support in kernel
ALTQ related functions disabled
pf enabled

   ▔▔▔▔▔▔▔ SHARE ZSCALER HOST CONFIGURATION

Configuring route to 10ß.200.0.0
route: writing to routing socket: not in table
delete net 100.200.0.0: not in table
add net 100.200.0.0: gateway 192.168.206.14
Configuring resolver for internal
Flushing DNS cache
Host configuration completed ✔
```


## Troubleshooting
- You can run the setup script as many times as you like.
- The output script to run on your local machine updates your name resolution accordingly,
  that is, it updates existing hosts and adds new ones.
- You will very likely have to update `SHARE_ZSCALER_SOURCE_ADDRESS` to the network used by your Parallels installation.
  - You can look it up by opening System Preferences → Network → Ethernet → IP Address
  - As an example: if the screen shows `192.168.42.3` you'll have to use `SHARE_ZSCALER_SOURCE_ADDRESS=192.168.42.0/24`
- If you happen to have no access anymore
  - check if Zscaler is actually connected
  - run (1) your customized `share-zscaler.sh` call on the VM and (2) its output script on your local machine again.
