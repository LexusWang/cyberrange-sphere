from mergexp import *

# Create a network topology object
net = Network('hello-world', addressing==ipv4, routing==static)

attacker = net.node('attacker', image=='kali', proc.cores>=8, memory.capacity>=gb(32), disk.capacity==gb(100))
redirector = net.node('redirector', image=='2404')
emailServer = net.node('emailServer', image=='2404')
victim1 = net.node('victim1', image=='2404', proc.cores==2, memory.capacity==gb(2), disk.capacity==gb(50))
victim2 = net.node('victim2', image=='2404', proc.cores==2, memory.capacity==gb(2), disk.capacity==gb(50))
victim3 = net.node('victim3', image=='2404', proc.cores==2, memory.capacity==gb(2), disk.capacity==gb(50))
victim4 = net.node('victim4', image=='2404', proc.cores==2, memory.capacity==gb(2), disk.capacity==gb(50))
victim5 = net.node('victim5', image=='windowstest', proc.cores==2, memory.capacity==gb(2), disk.capacity==gb(50))

# Create a link connecting the three nodes
link = net.connect([attacker,redirector,emailServer,victim1,victim2,victim3,victim4,victim5])

# Make this file a runnable experiment
experiment(net)