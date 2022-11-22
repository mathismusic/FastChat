#!/bin/sh
# runcmd="python3 server.py \"$1\" \"$2\" \"fastchat_users\""
cmd="cd Documents/Sem3/FastChat; python3 server.py $1 $2 $3" #192.168.103.215 61003
# echo $cmd
osascript -e "tell app \"Terminal\" to do script \"$cmd\""