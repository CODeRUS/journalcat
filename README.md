# journalcat.py
Script to print journalctl in colourful and smart way

Local usage:

`./journalcat.py -f -n 20 -ts -hl error`

Remote usage:

`ssh user@192.168.2.15 sudo journalctl -f -n 20 -o json | ./journalcat.py -ts -hl error`

Using `-o json` in remote is mandatory