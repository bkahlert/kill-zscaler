*Instructions on [how to share the connection of a Zscaler installed in a virtual machine](#sharing-zscaler) can be found below.*

# Killing Zscaler on macOS

Zscaler can be annoying if you're trying to stop it. Despite have administrative rights, usually it asks for a password.

Pick one of the following options to take back control.

## Using the App

People who prefer apps over command lines can use
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

To share an existing Zscaler connection you can use [share-zscaler.sh](share-zscaler.sh) on the machine
with Zscaler installed as follows:
```shell
SHARE_ZSCALER_SOURCE_ADDRESS=192.168.64.0/24 \
SHARE_ZSCALER_EXTERNAL_ADDRESS=10.100.0.0/16 \
SHARE_ZSCALER_HOSTS='
    example.com
    foo.bar.internal
' ./share-zscaler.sh
```

- The script will set up network address translation (NAT) so that traffic
from 192.168.64.x will be properly routed.
- It prints instructions on how to configure clients to actually 
pass their requests to your Zscaler machine for the specified domains.
- It copies a script to your clipboard that applies all just mentioned steps.

If you prefer to have a one-liner without having to download anything you can use the following
command *at your own risk*:
```shell
SHARE_ZSCALER_SOURCE_ADDRESS=192.168.64.0/24 \
SHARE_ZSCALER_EXTERNAL_ADDRESS=10.100.0.0/16 \
SHARE_ZSCALER_HOSTS='
    example.com
    foo.bar.internal
' bash -c "$(curl -so- https://raw.githubusercontent.com/bkahlert/kill-zscaler/main/share-zscaler.sh)"
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
      "$PARALLELS"/Contents/MacOS/prl_macvm_create "$VMDIR/macOS.ipsw" "$VMDIR/$NAME.macvm" --disksize 30000000000
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
   2. Create a macOS user
   3. Install Parallels Tools and reboot
   4. Install Zscaler
   5. Login
3. Establish connection
   1. Start Zscaler (if not already running)
   2. [Run share-zscaler.sh](#sharing-zscaler)
4. Use connection
   1. On your local machine open a terminal
   2. Paste the script (that was copied in the previous step to your clipboard) in the terminal and run it

**You can now connect to all hosts you listed in step 2** 🎉

Optionally you can set the name of your VM in
1. System Preferences → Network → Ethernet → Advanced... → WINS → NetBIOS Name
2. System Preferences → Sharing → Computer Name

## Remote Execution

This section describes the necessary steps to run `share-zscaler.sh` on your
local machine instead of the virtual Zscaler machine using SSH.

### Preparation

#### On your virtual machine
1. Activate SSH by checking System Preferences → Sharing → Remote Login

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

The example used in this chapter will change to the following in order to be executed
on the host `Zscaler` with user `zscaler`:
```shell
ssh -t zscaler@Zscaler.local '
SHARE_ZSCALER_SOURCE_ADDRESS=192.168.64.0/24 \
SHARE_ZSCALER_EXTERNAL_ADDRESS=10.100.0.0/16 \
SHARE_ZSCALER_HOSTS='"'"'
    example.com
    foo.bar.internal
'"'"' bash -c "$(curl -so- https://raw.githubusercontent.com/bkahlert/kill-zscaler/main/share-zscaler.sh)"'
```

You will be prompted for the password of user `zscaler`.  
After you ran the command you'll have the command to be executed locally in your clipboard and can just paste it.

You can even call `pbpaste | bash` to run that script directly.


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
