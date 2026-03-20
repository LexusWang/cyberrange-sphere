from mergexp import *

# Create a network topology object
net = Network('Redis-Unauth-Lab', addressing==ipv4, routing==static)

attacker = net.node('attacker', image=='kali', proc.cores>=8, memory.capacity>=gb(32))
victim = net.node('victim', image=='2404', proc.cores==2, memory.capacity==gb(2))

# Create a link connecting the two nodes
link = net.connect([attacker, victim])

# Assign fixed experiment network addresses so inventory.ini never needs updating
link[attacker].socket.addrs = ip4('10.0.0.1/24')
link[victim].socket.addrs   = ip4('10.0.0.2/24')

# Make this file a runnable experiment
experiment(net)
