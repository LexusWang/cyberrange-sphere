from mergexp import *

# Create a network topology object
net = Network('AD-Domain', addressing==ipv4, routing==static)

attacker = net.node('attacker', image=='kali', proc.cores>=8, memory.capacity>=gb(32))
victimDC = net.node('victimDC', image=='2404', proc.cores==2, memory.capacity==gb(2))
victim1 = net.node('victim1', image=='2404', proc.cores==2, memory.capacity==gb(2))
victim2 = net.node('victim2', image=='2404', proc.cores==2, memory.capacity==gb(2))
victim3 = net.node('victim3', image=='2404', proc.cores==2, memory.capacity==gb(2))
victim4 = net.node('victim4', image=='2404', proc.cores==2, memory.capacity==gb(2))
victim5 = net.node('victim5', image=='2404', proc.cores==2, memory.capacity==gb(2))

# Create a link connecting the three nodes
link = net.connect([attacker,victim1])
link = net.connect([victimDC,victim1,victim2,victim3,victim4,victim5])

# Make this file a runnable experiment
experiment(net)