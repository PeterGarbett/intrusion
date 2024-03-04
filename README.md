
intrusion.py
------------

An investigation into using yolo to remove false positives
when looking for people moving about.

opencv project - the time is mostly spent in long opencv
activities so python3 is reasonable. It's also neat to
be able to pass references to images through a queue.

This software has been developed on an 8Gb  raspberry pi 5.
Being multi core, reasonably fast and having hardware 
for video encode/decode makes it a good match.
It works with a logitech 720. Since I have a fixed setup
I don't indulge in a lot of camera capability investigation.

This software is an ongoing prototype I intend to get some
reasonable test data . I think passing a test video into it
rather than camera input should work for a lot of cases.



Installation notes:

I currently run this under my user account which some may 
think is a tad unproffesional.  Should be easy enough to change.

set runlevel to 3 via the command.
sudo systemctl set-default target multi-user.target
This is so it doesn't automount so I can keep a fixed name
for the mount point. It is run headless anyway.

I've kept the files I've used to mount the drive as a service
in mount-usb/ for reference.  There seem to be lots of ways to do this.
My main desire is to not change fstab as an error would make the
system unbootable. The mount makes this directory available:

sudo mount -t exfat /dev/sda1  /exdrive/ -o peter -o peter

I've had the program terminate fail due to memory exhaustion.
I've since made changes to how frequently I push items onto
the image analysis queue so this shouldn't occur . As an interim
fix I setup a 10Gb swapfile.

There are a few parameters set via a configuraion file "intrusion.conf" 
(with short explanations in that file) which I first search for on  
/exdrive/Snapshots/Local/ and fall back to /etc/intrusion/
i.e. one internal and one external search directory

Files with vauge hints about contents:
-------------------------------------


intrusion.conf			# Configuration data
intrusion.py			# Main program
intrusion.service		# To run program as a service
copySSHKeys.py			# Copy over .ssh content to setup external comms
readfile_ignore_comments.py	# Used to read configuration file.
setup				# When this grows up it will be a .deb 
mount-usb/			# files to mount (large) drive as external image store
yolo.py				# Interface to yolo software derived heaviliy from
				# the work of http://www.arunponnusamy.com

These files are needed by yolo.py, placed on /etc/opt/yolo/

yolov3.cfg
yolov3.txt
yolov3.weights


The yolo weights are too big to upload but can be found on 

https://github.com/arunponnusamy/object-detection-opencv.git
and are described on
https://towardsdatascience.com/yolo-object-detection-with-opencv-and-python-21e50ac599e9
 


