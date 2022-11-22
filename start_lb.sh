#!/bin/sh
cmd="cd Documents/Sem3/FastChat; python3 loadbalancer.py"
echo $@
echo $cmd
osascript -e "tell app \"Terminal\" to do script \"$cmd\""