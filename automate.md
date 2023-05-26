Automating script execution in Linux

\*\* For Linux users
Open your terminal and run the below line. Copy the output

```bash
which python3 # path to python3 executable usually /usr/bin/python3
```

Type the below and press enter

`$ crontab -e`

This opens crontab in your preferred editor.

Add the below line to your crontab.

`30 19 * * 1-5 <python3 path> <path to init.py> >> ~/Desktop/cron.log 2>&1`

- Replace <python3 path> with the output of `which python3`
- Replace \<path to init.py\> with the actual location of 'init.py'

This runs init.py Monday to Fri at 7:30 pm and stores the output to ~/Desktop/cron.log.

Save the file and exit.

**NSE Daily reports are updated after 7 pm, so ideally schedule script execution post 7 pm only.**
