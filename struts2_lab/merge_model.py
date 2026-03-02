from mergexp import *

# Create a network topology object
net = Network('Single-Victim', addressing==ipv4, routing==static)

attacker = net.node('attacker', image=='kali', proc.cores>=8, memory.capacity>=gb(32))
victim = net.node('victim', image=='2404', proc.cores==2, memory.capacity==gb(2))

# Create a link connecting the three nodes
link = net.connect([attacker,victim])

# Make this file a runnable experiment
experiment(net)