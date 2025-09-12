## This folder hosts materials for the POC exploit.

For ethical considerations, we cannot release the source code of the forged version of Baidu Input Method. Instead, we open-sourced the attack payload and the loader method (see the ExploitLoader folder) and uploaded the demonstration video to show the effectiveness of our POC exploit.

For the demo video:

* This video was taken on a Vivo X90 smartphone. 
* An exploitation of the pre-installed Baidu Input Method was implemented.
* Specifically, we adopted the malicious DEX injection strategy to forge a malicious version of the Baidu Input Method, with a newer version (11.6.12.17).
* After the user installs the malicious app as an update, the attacker can access and save all the user's keyboard input.
* An auxiliary app "AppSign" was implemented to facilitate this demo, which keeps reading the saved user keyboard input and displays it on the screen.
