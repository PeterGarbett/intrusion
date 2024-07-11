#!/bin/bash


# suppress the add ones we don't have in general

exit

echo "Clean up space before depowering"

#/home/embed/EOS/bin/python3 /home/embed/EOS/clear-space.py 

echo "Power down external camera - release lock  "

/home/embed/EOS/bin/python3 /home/embed/EOS/camera_pwr.py 

#a depowered camera should not be holding a lock

sudo rm -f /var/lock/canon20d.lock

