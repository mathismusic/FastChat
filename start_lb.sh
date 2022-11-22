#!/bin/sh
cmd="echo \'$@\' | python3 loadbalancer.py"
echo \'$@\' #cd Documents/Sem3/FastChat; 
echo $cmd
osascript -e "tell app \"Terminal\" to do script \"$cmd\""